import numpy as np
import copy
import statistics
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value, LpStatus
from .O41_dual_solver import DualProblem
    
class RewindProb(DualProblem):
  
  # have condition to decide proportion of orginal MC to cut # apply for many FG and 1 stock MC
  # then move to the linear problem -> to decide the trim loss only
  def __init__(self, finish, stock):
    super().__init__(finish, {} )
    self.ratio = 0.5 # default ratio --> NEED TO CONSIDER SMALLEST LEFT OVER ALLOWED
    self.stock_key = list(stock.keys())[0]
    self.og_weight = stock[self.stock_key]['weight']
    self.stock = stock
    
  def _rewind_ratio(self):
    # xac dinh ratio da phai tinh den weight cat
    coil_weight = [self.dual_finish[f]["need_cut"] * self.stock[self.stock_key]['width'] /self.dual_finish[f]["width"] for f in self.dual_finish.keys()]
    self.med_demand_weight= statistics.median(coil_weight) # cho phep cat du 1 chut
    
  def _check_rewind_coil(self):
    #remained rewind stock weight should be in this range 
    min_coil_weight = [self.dual_finish[f]["Min_weight"] * self.stock[self.stock_key]['width'] /self.dual_finish[f]["width"] for f in self.dual_finish.keys()]
    # max_coil_weight = [self.dual_finish[f]["max_weight"] * self.stock[self.stock_key]['width'] /self.dual_finish[f]["width"] for f in self.dual_finish.keys()]
    min_w = statistics.median(min_coil_weight)
    # max_w = statistics.median(max_coil_weight)
    return min_w
  
  def create_new_stocks_set(self ):
    self._rewind_ratio()
    min_w= self._check_rewind_coil()
    
    #create new set stock if remained weight not to small
    if min_w < self.og_weight - self.med_demand_weight:
      for i in range(2):
        self.dual_stocks[f'{self.stock_key}-{i+1}'] = self.stock[self.stock_key]
        if i < 1: 
          self.dual_stocks[f'{self.stock_key}-{i+1}'].update({'weight':self.med_demand_weight})
          # print(f"cut rewind weight {self.med_demand_weight}")
        else: 
          self.dual_stocks[f'{self.stock_key}-{i+1}'].update({'weight': self.og_weight - self.med_demand_weight}) # we have new set of stock
        self.dual_stocks[f'{self.stock_key}-{i+1}'].update({'status':"R:REWIND"})
        
      self.start_stocks = copy.deepcopy(self.dual_stocks)
    else:
      pass

     
  

  
  