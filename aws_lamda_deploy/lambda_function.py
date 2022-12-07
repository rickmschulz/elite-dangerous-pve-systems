import json
import pandas as pd
import pygsheets
import requests
import re
from bs4 import BeautifulSoup as bs
import csv
from time import sleep
import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import datetime

# ------------------------------------------------------------------------

def save_excel(df):
    file = 'service_file.json'

    client = pygsheets.authorize(service_file=file)

    # Open the spreadsheet and the first sheet.
    sh = client.open('Elite_PVE')
    wks = sh.sheet1
    wks.clear()
    wks.set_dataframe(df, (1, 1))
    wks.replace("|", "\n")

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_day = now.strftime("%d/%m/%y")

    wks.append_table(values=[f'Updated: {current_day} at {current_time} UTC'])

# ------------------------------------------------------------------------
# MAIN LAMBDA FUNCTION
# ------------------------------------------------------------------------

def lambda_handler(event, context):

    with open('unique_factions.json') as f:
        parsed = json.load(f)
        data = json.dumps(parsed, indent=2)
        print(data)
        
    df_final = pd.read_csv('candidates_csv.csv', sep=';', index_col=0)

    df_final['INARA'] = None
    df_final['Factions Updated Time'] = None

    def check_faction_state(state):
        bag_of_words = ['war', 'election', 'civil war']
        if any(word in state.lower() for word in bag_of_words):
            return True
        
    count = 0
    for df_index, system_data in enumerate(df_final['Target/Sources']):
        count += 1
        systems = set()
        for key, value in parsed[system_data].items():
            systems.add(value[-1].split(',')[0].strip())
            
        system_index = 0
        fac_list = []
        for system in systems:
            system_index += 1
            param = dict()
            param['search'] = system
            url = 'https://inara.cz/starsystem'
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 Edg/103.0.1264.71",
            }
            
            # Request
            r = requests.get(url, params=param, headers=headers)

            # Soup
            soup = bs(r.content, 'lxml')
            
            # Checking factions updated time
            fac_updated = soup.find(string='Factions updated')
            
            if fac_updated:
                fac_updated = fac_updated.next_element.string
                
                if system_index % 2 == 0:
                    fac_list.append(system + ': ' + fac_updated)
                    df_final.loc[df_index, 'Factions Updated Time'] = ' | '.join(fac_list)
                    fac_list.clear()
                    
                elif system_index % 1 == 0:
                    fac_list.append(system + ': ' + fac_updated)

            table_data = soup.body.find('table', class_='tablesorter')

            keep_going = True
            for index, tr in enumerate(table_data.find_all('tr')):
                if not keep_going:
                    break
                elif index > 0:
                    for i, td in enumerate(tr.find_all('td')):
                        if (i == 3 or i == 4) and check_faction_state(td.text.strip()):
                            df_final.loc[df_index, 'INARA'] = 'war, election or civil war detected'
                            keep_going = False
                            break
        
            sleep(r.elapsed.total_seconds())

    save_excel(df_final)
