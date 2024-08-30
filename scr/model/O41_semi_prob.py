### LOAD FINISH AND MOTHER COIL BY PARAMS - CUSTOMER
import pandas as pd
import numpy as np
import copy

from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value, LpStatus
from .O31_steel_objects import FinishObjects, StockObjects


# DEFINE PROBLEM
class SemiProb():
  def __init__(self, stocks, finish,PARAMS):
    self.S = StockObjects(stocks, PARAMS)
    self.F = FinishObjects(finish, PARAMS)
    self.skey = list(stocks.keys())[0]
    self.fkey = list(finish.keys())[0]
    self.taken_stocks ={}
    
  def _max_loss_margin_by_wh(self,margin_df):
    # xac dinh max margin cho phep voi loai Z:SEMI MCOIL
    wh_list = margin_df['coil_center'].unique().tolist()
    self.max_margin_semi ={}
    for wh in wh_list:
      wh_df = margin_df[margin_df['coil_center'] == wh]
      self.max_margin_semi[wh] = max(wh_df['Min Trim loss (mm)']) # ap dung cho th khong biet width coil goc 
      
  def _set_stock_finish(self):
    self.finish = self.F.finish
    self.stock = self.S.stocks
  
  def update(self, margin_df):
    self.F.update_bound(3) # take max bound = 3
    self.S.update_min_margin(margin_df)
    self._set_stock_finish()
    self.remained_stocks= self.stock
    self._max_loss_margin_by_wh(margin_df)
  
  def _cut_patterns(self):
    # to satisfy upperbound weight -> how many lines to cut
    self.num_cuts_by_weight = round(
          self.finish[self.fkey]['upper_bound'] /
          (self.stock[self.skey]['weight'] * self.finish[self.fkey]['width'] / self.stock[self.skey]['width'] )
      )
    self.num_cuts_by_width = int(
          (self.stock[self.skey]["width"] - self.stock[self.skey]["min_margin"]) / 
          self.finish[self.fkey]["width"]
      )
  
  # chua margin bang 1/2 margin goc
  def _semi_cut_ratio(self):
    rmark = self.stock[self.skey]['remark'] #
    
    if self.stock[self.skey]['status'] == "Z:SEMI MCOIL" and "cut_dict" not in rmark: # cat tiep tu 1 coil semi, ap dung truong hop ko co remark do model generate tu truoc
      print("cat tu cuon SEMI") # allowed margin?
      # check margin con lai < max margin ko/// BUOC PHAI CAT HET ?
      margin = self.stock[self.skey]["width"] - self.num_cuts_by_width * self.finish[self.fkey]["width"]
      wh = self.stock[self.skey]['warehouse']
      if margin < (self.max_margin_semi[wh]*2):
        self.cut_dict = {str(self.fkey): self.num_cuts_by_width}
        self.remained_stocks = {}
        self.taken_stocks = self.stock
      else: 
        self.cut_dict = {str(self.fkey): 0}
        self.remained_stocks = self.stock
      
    elif self.stock[self.skey]['status'] == "Z:SEMI MCOIL" and "cut_dict" in rmark:
      # print("cat theo cut dict")
      new_rmark = rmark.replace("cut_dict", "")
      # Split the string into key and value
      key, value = new_rmark.split(":")
      # Convert to a dictionary
      self.cut_dict = {key: value}
      # check if key = FG codes?
      self.remained_stocks = {}
      self.taken_stocks = self.stock
      
    elif self.stock[self.skey]['status'] == "M:RAW MATERIAL":  #hoac cat ra tu Mother coil phan biet bang status.
      print("cat tu cuon RAW MC")
      self.cut_width = self.num_cuts_by_weight * self.finish[self.fkey]['width']
      self.remained_cuts = self.num_cuts_by_width - self.num_cuts_by_weight
      self.remain_width = self.stock[self.skey]['width'] - self.cut_width - (self.stock[self.skey]['min_margin']/2)  # chua bien 1 ben
    
    else: 
      pass
    
  def _check_remain_width(self):
    # case nay giong nhu check Z:SEMI MCOIL, ghi lai Remark cach cat nhu dict-cut
    # wh = self.stock[self.skey]['warehouse']
    cond = ((self.remain_width 
            #  - (self.stock[self.skey]['min_margin'])      \
             - self.remained_cuts * self.finish[self.fkey]['width']) < self.stock[self.skey]['width'] * 0.04
            )
    return cond
  
  def cut_n_create_new_stock_set(self):
    self._cut_patterns()
    self._semi_cut_ratio() # cut_dict cho loai Z: SEMI
    if self.stock[self.skey]['status'] == "M:RAW MATERIAL":
      cond = self._check_remain_width()
      if cond == True:
        self.cut_dict = {str(self.fkey): self.num_cuts_by_weight}
        self.cut_weight = self.num_cuts_by_weight*self.finish[self.fkey]['width'] * self.stock[self.skey]['weight'] /self.stock[self.skey]['width']
        self.over_cut = {str(self.fkey): round(self.cut_weight - self.finish[self.fkey]['need_cut'],3)}
        self.taken_stocks = {f'{self.skey}-Se1':{"receiving_date": self.stock[self.skey]['receiving_date'],
                                                  "width": self.cut_width + self.stock[self.skey]['min_margin']/2,
                                                  "weight": self.cut_width/self.stock[self.skey]['width']*self.stock[self.skey]['weight'],
                                                  "warehouse": self.stock[self.skey]['warehouse'],
                                                  'status': "Z:SEMI MCOIL",
                                                  "remark":f"cut_dict{self.fkey}:{self.remained_cuts}"}}
        self.remained_stocks = {f'{self.skey}-Se2':{"receiving_date": self.stock[self.skey]['receiving_date'],
                                                    "width": self.remain_width,
                                                    "weight": self.remain_width/self.stock[self.skey]['width']*self.stock[self.skey]['weight'],
                                                    "warehouse": self.stock[self.skey]['warehouse'],
                                                    'status': "Z:SEMI MCOIL",
                                                    "remark":f"cut_dict{self.fkey}:{self.remained_cuts}"}}        
      else: 
        self.cut_dict = {str(self.fkey): 0} # ko cat duoc
        self.over_cut = {str(self.fkey): - self.finish[self.fkey]['need_cut']}
        self.remained_stocks = self.stock
        self.taken_stocks = {}
    
if __name__ == "__main__":
  PARAMS = {
            "spec_name": "JSC270C-SD",
            "type": "Carbon",
            "thickness": 2.0,
            "maker": "POSCOVN",
            "code": "POSCOVN JSC270C-SD 2.0"
         }
  stocks = {
            "TZ241H12000011": {
               "receiving_date": 45202,
               "width": 1049,
               "weight": 4415,
               "warehouse": "HSC",
               "status":"M:RAW MATERIAL",
               "remark":""
            }
         }
  finish = {"F524": {   "customer_name": "VPIC1",   "width": 85.0,   "need_cut":- 350.0,  
                     "fc1": 114.8576,   "fc2": 93.372,   "fc3": 114.7572, 
                     "1st Priority": "HSC",   "2nd Priority": "x",   "3rd Priority": "x",  
                     "Min_weight": 0.0,   "Max_weight": 0.0
                  }
               }
  margin_df = pd.read_csv('scr/model_config/min_margin.csv')
  spec_type = pd.read_csv('scr/model_config/spec_type.csv')
  
  steel = SemiProb(stocks, finish, PARAMS)
  steel.update(margin_df)
  steel.cut_n_create_new_stock_set()
  print(f"cuts: {steel.cut_dict}")
  print(f"taken stocks: {steel.taken_stocks}")