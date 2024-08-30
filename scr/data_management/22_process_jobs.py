import pandas as pd
import numpy as np
import json
import datetime
import copy

# INPUT
# fin_file_path = "scr/data/20240815_finish_df.xlsx"
# mc_file_path = "scr/data/20240815_mc_df.xlsx"
# spec_type_df = pd.read_csv('scr/model_config/spec_type.csv')

# SETUP
finish_key = 'order_id'
finish_columns = ["customer_name", "width", "need_cut", 
                  "fc1", "fc2", "fc3", "average FC",
                  "1st Priority", "2nd Priority", "3rd Priority",
                  "Min_weight", "Max_weight"
                  ]
stock_key = "inventory_id"
stock_columns = ['receiving_date',"width", "weight",'warehouse',
                 "status",'remark'
                 ]
def div(numerator, denominator):
    def division_operation(row):
        if row[denominator] == 0:
            if row[numerator] > 0:
                return np.inf
            elif row[numerator] < 0:
                return -np.inf
            else:
                return np.nan  # Handle division by zero with numerator equal to zero
        else:
            return float(row[numerator] / row[denominator])
    return division_operation

def create_finish_dict(finish_df):
  
    finish_df.loc[:, 'stock_ratio'] = finish_df.apply(div('need_cut', 'average FC'), axis=1)
    can_cut_df = finish_df[finish_df['stock_ratio'] < 0.5] # Co the cat du cho hang ko co need cut am
    sorted_df = can_cut_df.sort_values(by=['need_cut','width'], ascending=[True,False]) # need cut van dang am
    
    # Initialize result dictionary - take time if the list long
    finish = {f"F{int(row[finish_key])}": {column: row[column] for 
                                          column in finish_columns} for 
                                          _, row in sorted_df.iterrows()}
    return finish

def create_stocks_dict(stock_df):
    # Sort data according to the priority of FIFO
    sorted_df = stock_df.sort_values(by=['width','weight','receiving_date',], ascending=[ False,False,True,])
    # Set the index of the DataFrame to 'stock_id'
    sorted_df.set_index(stock_key, inplace=True)
    # Convert DataFrame to dictionary
    sorted_df[stock_columns] = sorted_df[stock_columns].fillna("") 
    stocks = sorted_df[stock_columns].to_dict(orient='index')
   

    return stocks

def filter_by_params(file_path,params):
    # Read the Excel file into a DataFrame
    df = pd.read_excel(file_path)

    filtered_df = df[
                    (df["spec_name"] == params["spec_name"]) & 
                    (df["thickness"] == params["thickness"]) &
                    (df["maker"] == params["maker"])
                    ]
    return filtered_df

def filter_fininsh_by_params(file_path,params):
    # Read the Excel file into a DataFrame
    df = pd.read_excel(file_path)

    filtered_df = df[(df["customer_name"] == params["customer"]) & 
                    (df["spec_name"] == params["spec_name"]) & 
                    (df["thickness"] == params["thickness"]) &
                    (df["maker"] == params["maker"])
                    ]
    return filtered_df

def find_spec_type(spec,spec_type_df):
    try:
        type = spec_type_df[spec_type_df['spec']==spec]['type'].values[0]
    except IndexError:
        type = "All"
    return type

# PROCESS
if __name__ == "__main__":
    
    today = datetime.datetime.today()
    formatted_date = today.strftime("%d-%m-%y")

    finish_list = {
        'date': formatted_date,
        'param_finish':{}
    }
    stocks_list = {
        'date': formatted_date,
        'param_finish':{}
    }

    with open(f'scr/jobs_by_day/job-list-{formatted_date}.json', 'r') as file:
        job_list = json.load(file)

    for job in job_list['jobs']: 
        # loop to create stock list
        PARAMS = {}
        param = job['param']
        param_split = param.split("+")
        maker = param_split[0]
        spec = param_split[1]
        thickness = round(float(param_split[2]),2)

        PARAMS = {
                    "spec_name" :spec,
                    "type"      : find_spec_type(spec,spec_type_df),
                    "thickness" :thickness,
                    "maker"     : maker,
                    "code"      : maker + " " + spec  + " " + str(thickness)
                    }

        mc_df = filter_by_params(mc_file_path, PARAMS)
        stocks = create_stocks_dict(mc_df)

        stocks_list['param_finish'][param] = {'param': PARAMS, 'stocks': stocks}
        finish_list['param_finish'][param] = {'param': PARAMS, 'customer':[]}
        for cust, value in job['tasks'].items():
            # loop to create finish list accordingly with params and customer
            PARAMS1 = {
                    'customer'  :cust,
                    "spec_name" :spec,
                    "type"      : find_spec_type(spec,spec_type_df),
                    "thickness" :thickness,
                    "maker"     : maker,
                    "code"      : maker + " " + spec  + " " + str(thickness)
                    }
            finish_df = filter_fininsh_by_params(fin_file_path, PARAMS1)
            finish = create_finish_dict(finish_df)
            finish_list['param_finish'][param]['customer'].append({cust: finish})
        
    with open(f'scr/jobs_by_day/stocks-list-{formatted_date}.json', 'w') as stocks_file:
        json.dump(stocks_list, stocks_file, indent=3)

    with open(f'scr/jobs_by_day/finish-list-{formatted_date}.json', 'w') as json_file:
        json.dump(finish_list, json_file, indent=3)
