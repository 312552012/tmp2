### Before running, plz setup variable:config[GRU][feature_selection_index] and config[GRU][dummy]
### generate company_buy from 2019-3~2022-1 
### python generate_company_buy_GRU.py path=?

import pickle
import statistics
import sys
import os
import configparser
import json
import pandas as pd

import torch.nn as nn
import torch
from model import GRU


config = configparser.ConfigParser()    
config.read('config.ini')

NUMBER_OF_COMPANY = 97
NumberOfFeatures = 18
number_of_quarters_per_stock = 37

if config['GRU']['dummy'].lower() == 'true':
    ifDummy = True
elif config['GRU']['dummy'].lower() == 'false':
    ifDummy = False
else:
    raise RuntimeError('dummy must be true or false')

input = pd.read_csv('ratio-2022-12-13.csv', dtype='str', keep_default_na=False)
sector_dict = {
    'Technology': 0,
    'Energy': 1,
    'Consumer Cyclical': 2,
    'Industrials': 3,
    'Consumer Defensive': 4,
    'Real Estate': 5,
    'Financial Services': 6,
    'Communication Services': 7,
    'Basic Materials': 8
}
company_list = []
sector_list = []
for i in range(0, number_of_quarters_per_stock * NUMBER_OF_COMPANY, number_of_quarters_per_stock):
    company_list.append(input['Name'][i])
    sector_list.append(sector_dict[input['Sector'][i]])

def isMissing(input):
    return input == '' or input == 'nan'

company_buy_index = []
for simulation_num in range(24, 35):
    #load ratio
    input = pd.read_csv('ratio-2022-12-13.csv', dtype='str', keep_default_na=False)
    
    ratio_raw = input.drop(labels='CO_ID', axis=1)
    ratio_raw = ratio_raw.drop(labels='Name', axis=1)
    ratio_raw = ratio_raw.drop(labels='Year', axis=1)
    ratio_raw = ratio_raw.drop(labels='Quarter', axis=1)
    ratio_raw = ratio_raw.drop(labels='Sector', axis=1)
    ratio_raw = ratio_raw.drop(labels='Stock Return', axis=1)

    ratio_raw = ratio_raw.values.tolist()
    
    ratio = []
    for i in range(0, number_of_quarters_per_stock * NUMBER_OF_COMPANY, number_of_quarters_per_stock):
        ratio_for_one_company_in_right_order = []
        for j in range(i, i + number_of_quarters_per_stock):
            ratio_for_one_company_in_right_order.append(ratio_raw[j])
        ratio.append(ratio_for_one_company_in_right_order)


    #determine scope of feature
    ratio_scope = []
    for i in range(NUMBER_OF_COMPANY):
        ratio_scope.append(ratio[i][simulation_num-24:simulation_num+3])

    #補空缺資料:若至少有一個資料點,則補平均,若無則補-1
    for i in range(NUMBER_OF_COMPANY):     
        for k in range(NumberOfFeatures):
            nonMissingCount = 0
            sum = 0.0
            for j in range(len(ratio_scope[i])):
                if not isMissing(ratio_scope[i][j][k]):
                    ratio_scope[i][j][k] = float(ratio_scope[i][j][k].replace(',', ''))
                    sum += ratio_scope[i][j][k]
                    nonMissingCount += 1
            if nonMissingCount:
                mean = sum / nonMissingCount
                for j in range(len(ratio_scope[i])):
                    if isMissing(ratio_scope[i][j][k]):
                        ratio_scope[i][j][k] = mean
            else:
                for j in range(len(ratio_scope[i])):
                    ratio_scope[i][j][k] = -1.0
    
    #standardization
    mean = []
    stdev = []
    for k in range(NumberOfFeatures):
        arr = []
        for i in range(NUMBER_OF_COMPANY):
            for j in range(len(ratio_scope[i])):
                arr.append(ratio_scope[i][j][k])
        mean.append(statistics.mean(arr))        
        stdev.append(statistics.stdev(arr))

    for i in range(NUMBER_OF_COMPANY):
        for j in range(len(ratio_scope[i])):
            for k in range(NumberOfFeatures):
                ratio_scope[i][j][k] = (ratio_scope[i][j][k] - mean[k]) / stdev[k]
    
    if ifDummy:
        for i in range(NUMBER_OF_COMPANY):
            dummy_vector = [0 for _ in range(len(sector_dict) - 1)]
            if sector_list[i] != 8:
                dummy_vector[sector_list[i]] = 1
            for j in range(len(ratio_scope[i])):
                ratio_scope[i][j] = ratio_scope[i][j] + dummy_vector

    X = []
    for i in range(NUMBER_OF_COMPANY):
        X.append(ratio_scope[i][-4:])
    X = torch.Tensor(X)

    #prepare model
    year = (simulation_num - 2) // 4 + 2014
    quarter = (simulation_num - 2) % 4 + 1
    model_path = sys.argv[1].split('=')[1] + '/' + str(year) + '-' + str(quarter) + '.pth'
    if ifDummy:
        model = GRU(NumberOfFeatures + len(sector_dict) - 1, 36, 1, dropout=0.2)
    else:
        model = GRU(NumberOfFeatures, 36, 1, dropout=0.2)
    model.load_state_dict(torch.load(model_path))
    model.eval()

    #predict
    predict = model(X)
    predict = predict.squeeze()
    predict = predict.tolist()

    #generate quarter_company_buy
    quarter_company_buy = sorted(range(len(predict)), key=lambda k: predict[k])
    quarter_company_buy.reverse()
    company_buy_index.append(quarter_company_buy)


company_buy_name = []
for quarterly_buy in company_buy_index:
    temp = [company_list[index] for index in quarterly_buy]
    company_buy_name.append(temp)

with open("company_buy_index.pickle", "wb") as fp:
    pickle.dump(company_buy_index, fp)

with open("company_buy_index_3.pickle", "wb") as fp:
    pickle.dump(company_buy_index, fp)

with open("company_buy_name.pickle", "wb") as fp:
    pickle.dump(company_buy_name, fp)