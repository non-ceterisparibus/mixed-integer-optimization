import numpy as np
import pandas as pd
import copy
import statistics
from .O31_steel_objects import FinishObjects, StockObjects
from .O41_dual_solver import DualProblem
from .O41_rewind_prob import RewindProb

from pulp import LpMaximize, LpMinimize, LpProblem, LpVariable, lpSum, PULP_CBC_CMD, value

# DEFINE PROBLEM
class CuttingStocks:
    def __init__(self, finish, stocks, PARAMS):
        self.S = StockObjects(stocks, PARAMS)
        self.F = FinishObjects(finish, PARAMS)
        self.over_cut = None

    def update(self, bound, margin_df):
        self.F.update_bound(bound)
        self.S.update_min_margin(margin_df)
     
    def _stock_weight_threshold_by_width(self, min_w, max_w):
        """_Create a diction of min and weight of coil that will produce same div of FG_

        Args:
            min_w (_int_): Min Weight of Cut Coil by Customer x FG Codes
            max_w (_int_): Max Weight of Cut Coil by Customer x FG Codes
        Result:
        {1080: {'min': 1588.235294117647,
                'max': [2842.1052631578946,
                        5684.210526315789,
                        8526.315789473683,
                        11368.421052631578]},
        1219: {'min': 1792.6470588235295,
               'max': [3207.8947368421054,
                        6415.789473684211,
                        9623.684210526317,
                        12831.578947368422]}}
        """
        
        self.stock_width =list(set([sv['width'] for _ ,sv in self.S.stocks.items()]))
        max_f_width = max([fv['width'] for _, fv in self.F.finish.items()])
        min_f_width = min([fv['width'] for _, fv in self.F.finish.items()])
        self.mm_stock_weight = {}
        for c_width in self.stock_width:
            # find weight range with min-max weight
            # min
            if min_w == 0.0:
                min_coil_weight = 0
            else:
                min_coil_weight = min_w * c_width/min_f_width
            # max
            if max_w == 0.0:
                max_coil_weight = float('inf')
            else:
                max_coil_weight = max_w * c_width/ max_f_width
            
            # check if min_coil_weight << max_coil_weight

            max_threshold = []
            for i in range(4):
                max_t = max_coil_weight * (i+1)
                max_threshold.append(max_t)
            self.mm_stock_weight[c_width] = {"min":min_coil_weight, "max": max_threshold}

    def _filter_min_stock(self):
        "Remove MC that too small, 1 line cut [weight] < Min Weight "
        self.filtered_stocks ={}
        for s_width, sv in self.mm_stock_weight.items():
            min_w = sv['min']
            filtered_min_stocks = {k: v for k, v in self.S.stocks.items() if (v['width'] == s_width and v['weight'] >= min_w)}
            self.filtered_stocks.update(filtered_min_stocks)
        
    def filter_stocks(self, min_weight = None,max_weight = None):
        if min_weight == None  and max_weight == None:
            self.filtered_stocks = copy.deepcopy(self.S.stocks)
        else:
            self._stock_weight_threshold_by_width(min_weight, max_weight)
            self._filter_min_stock()

    def set_prob(self, prob_type):
        if len(self.filtered_stocks) > 0 and prob_type == "Dual":
            # Initiate problem 
            self.prob = DualProblem(self.F.finish, self.filtered_stocks)
            return True # continue to run solve prob
        elif len(self.filtered_stocks) > 0 : 
            self.prob = RewindProb(self.F.finish, self.filtered_stocks)
            self.prob.create_new_stocks_set()
            return True
        else: #ko co stock de cat
            return False

    # Phase 5: Evaluation Over-cut / Stock Ratio
    def _count_weight(self):
        # Initialize an empty dictionary for the total sums
        total_sums = {}
        # Loop through each dictionary in the list
        for entry in self.prob.final_solution_patterns:
            count = entry['count']
            cuts = entry['cut_w']

            # Loop through each key in the cuts dictionary
            for key, value in cuts.items():
                # If the key is not already in the total_sums dictionary, initialize it to 0
                if key not in total_sums:
                    total_sums[key] = 0
                # Add the product of count and value to the corresponding key in the total_sums dictionary
                total_sums[key] += round(count * value,2)
        return total_sums

    def _calculate_div_ratio(self,s):
        """
        {1080: {'min': 1588.235294117647,
                'max': [2842.1052631578946,
                        5684.210526315789,
                        8526.315789473683,
                        11368.421052631578]},
        1219: {'min': 1792.6470588235295,
               'max': [3207.8947368421054, 3 2
                        6415.789473684211, 2 3
                        9623.684210526317, 1 4
                        12831.578947368422]}} 0 5
        """
        # doi chieu stock weight voi range max in mm_stock_weight by stock_width
        stocks_width = self.prob.start_stocks[s]['width']
        to_verify_range = sorted(self.mm_stock_weight[stocks_width]['max'], reverse=True)
        self.div_ratio = 0
        for i, w in enumerate(to_verify_range):
            if self.prob.start_stocks[s]['weight'] >= w:
                self.div_ratio =  (3-i) + 2
                break
    
    def _calculate_finish_after_cut_by_mm_weight(self):
        # for all orginal finish, not only dual
        if self.prob.probstt == "Solved":
            for i, sol in enumerate(self.prob.final_solution_patterns):
                s = self.prob.final_solution_patterns[i]['stock'] # stock cut
                self._calculate_div_ratio(s)
                cuts_dict = self.prob.final_solution_patterns[i]['cuts']
                weight_dict = {f: round(cuts_dict[f] * self.F.finish[f]['width'] * self.prob.start_stocks[s]['weight']/self.prob.start_stocks[s]['width'],3) for f in cuts_dict.keys()}
                if self.div_ratio == 0: 
                    rmark_note = "" 
                else: rmark_note = f"chat {self.div_ratio} phan"
                self.prob.final_solution_patterns[i] = {**sol, 
                                                        "cut_w": weight_dict,
                                                        }
                self.prob.final_solution_patterns[i].update({"remark": rmark_note})
            # Total Cuts
            total_sums = self._count_weight()
            self.over_cut = {k: round(total_sums[k] - self.F.finish[k]['need_cut'],3) for k in total_sums.keys()} # can tinh overcut cho moi finish, du ko duoc cat trong list dual finish
        else: pass # ko co nghiem trong lan chay truoc do
    
    def _calculate_finish_after_cut(self):
        # for all orginal finish, not only dual
        if self.prob.probstt == "Solved":
            for i, sol in enumerate(self.prob.final_solution_patterns):
                s = self.prob.final_solution_patterns[i]['stock'] # stock cut
                # self._calculate_div_ratio(s)
                cuts_dict = self.prob.final_solution_patterns[i]['cuts']
                weight_dict = {f: round(cuts_dict[f] * self.F.finish[f]['width'] * self.prob.start_stocks[s]['weight']/self.prob.start_stocks[s]['width'],3) for f in cuts_dict.keys()}

                self.prob.final_solution_patterns[i] = {**sol, 
                                                        "cut_w": weight_dict,
                                                        }
            # Total Cuts
            total_sums = self._count_weight()
            self.over_cut = {k: round(total_sums[k] - self.F.finish[k]['need_cut'],3) for k in total_sums.keys()} # can tinh overcut cho moi finish, du ko duoc cat trong list dual finish
        else: pass # ko co nghiem trong lan chay truoc do
    
    def solve_prob(self):
        # Run and calculate results
        self.prob.run()
        self._calculate_finish_after_cut()
        
        return self.prob.probstt, self.prob.final_solution_patterns, self.over_cut

    def _check_remain_stocks(self):
        # Extract stocks from final_solution_patterns
        taken_stocks = {p['stock'] for p in self.prob.final_solution_patterns} 
        # Update need cut
        for f, f_info in self.prob.dual_finish.items():
            if self.over_cut[f] < 0:
                f_info['need_cut'] = -self.over_cut[f]
            else: 
                f_info['need_cut'] = 0
                f_info['upper_bound'] += -self.over_cut[f]
                
        # Find remained_stocks dictionary
        self.remained_stocks = {
            s: {**s_info}
            for s, s_info in self.prob.dual_stocks.items()
            if s not in taken_stocks
        }
        
    def check_status(self):
        self._check_remain_stocks()
        # CHECK FOR ANOTHER ROUND
        if not self.prob.overused_list or not self.remained_stocks:
            print("FINISH CUTTING")
            return False
        else:
            # go back
            print("CONTINUE CUTTING")
            return True
        
    def refresh_data(self):
        self.prob.dual_stocks = copy.deepcopy(self.remained_stocks)
