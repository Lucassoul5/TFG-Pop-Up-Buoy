# -*- coding: utf-8 -*-
"""
Created on Sat Apr 20 11:42:55 2024

@author: LUCAS
"""
#Llibreries
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import matplotlib.dates as mdates
import numpy as np
import requests
import json 
import xmltodict 
import io
from io import StringIO

#%% API

#Sol·licitem les dades de la web d'Argos i les transformem en format csv

url = "http://ws-argos.cls.fr/argosDws/services/DixService"

payload = """<soap:Envelope xmlns:soap=\"http://www.w3.org/2003/05/soap-envelope\"
                 xmlns:typ=\"http://service.dataxmldistribution.argos.cls.fr/types\">
                 <soap:Header/>
                 <soap:Body>
                 <typ:csvRequest>
                 <typ:username>LUCAS</typ:username>
                 <typ:password>LUCAS</typ:password>
                 <typ:platformId>217475,217089,217459,217271,216875,217124</typ:platformId>
                 <typ:period>
                 <typ:startDate>2024-09-05T00:00:00</typ:startDate>
                 </typ:period>
                 <typ:referenceDate>MODIFICATION_DATE</typ:referenceDate>
                 <typ:displayDiagnostic>true</typ:displayDiagnostic>
                 <typ:displayMessage>true</typ:displayMessage>
                 <typ:displayCollect>true</typ:displayCollect>
                 <typ:displayRawData>true</typ:displayRawData>
                 <typ:displaySensor>true</typ:displaySensor>
                 <typ:argDistrib>A</typ:argDistrib>
                 <typ:showHeader>true</typ:showHeader>
                 </typ:csvRequest>
                 </soap:Body>
             </soap:Envelope>"""

response = requests.request("POST", url, data=payload)
dom = response.text

dom=dom.split("\r\n")

csv = dom[6]
csv = xmltodict.parse(csv)
csv = json.dumps(csv)

csv = json.loads(csv)
prov = csv['soap:Envelope']['soap:Body']['csvResponse']['return']

#%% Tractament de la resposta de l'API

lines = prov.split('\n')  #Separem la resposta per línies
truncated_lines = [line.split(';')[:57] for line in lines]  #Eliminem les dades més enllà de la columna 57 (són NaNs erronis)
truncated_data = '\n'.join(';'.join(line) for line in truncated_lines)  #Reunim les línies ara que tenen la mateixa longitud

original_data = pd.read_csv(io.StringIO(truncated_data), sep=';') #Generem un dataframe
original_data.index += 1 #Determinem que el primer valor del índex sigui el 1 i no el 0

#Modifiquem els noms de les columnes i eliminem les que no ens interesen
headers = ["delete","Platform ID","delete","delete","delete","Satellite","delete","Duration","Num Msg","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","delete","Msg Date","delete","delete","RawData","delete","delete","delete","delete","delete","delete","CRC","delete","delete","delete","Bits CRC","delete","delete","delete","delete","HexCounter","delete","delete","delete","delete","PWR","delete"]
original_data.columns = headers
delete_columns = [col for col in original_data.columns if 'delete' in col]
original_data = original_data.drop(columns=delete_columns)

#Eliminem caràcters prescindibles de les columnes amb temps
time_columns = ['Msg Date']
original_data[time_columns] = original_data[time_columns].replace({'.000Z': ''}, regex=True)
original_data[time_columns] = original_data[time_columns].replace({'T': ' '}, regex=True)

original_data = original_data.sort_values(by='Msg Date') #Ordenem les dades en ordre cronològic

#Separem la raw data en les diferents parts de les que es composa
def agrupar_cadena(RawData):
    RawData=str(RawData)
    grupos = [RawData[0:8], RawData[22:30], RawData[12:22], RawData[8:12]]
    return grupos

original_data['RawData_treatment'] = original_data['RawData'].apply(agrupar_cadena)
data = pd.DataFrame(original_data['RawData_treatment'].tolist(), columns=['Header', 'Footer', 'HexPWR', 'Comptador']) #Associem les diferents separacions del raw data al dataframe amb els noms adients
original_data.index = range(1, len(original_data)+1) #Establim l'index del tractament RawData amb inici a l'1
data.index = range(1, len(data) + 1)
parser = pd.concat([original_data, data], axis = 1)
datamsg = parser.drop('RawData_treatment', axis=1)

def hex_to_int(hex_str):
    if pd.isna(hex_str):
        return hex_str
    else:
        try:
            return int(hex_str, 16)
        except ValueError:
            return hex_str

datamsg['Counter'] = datamsg['HexCounter'].apply(hex_to_int) #Convertim el counter hexadecimal a decimal en una nova columna
datamsg['PWR'] =pd.to_numeric(datamsg['PWR'], errors='coerce') #Convertim la columna PWR a integer (els errors es queden en NaN)

datamsg = datamsg[['Platform ID','Satellite','Msg Date','Duration','Num Msg','RawData','CRC','Bits CRC','HexCounter','Counter','HexPWR','PWR','Header', 'Footer']] #Reubiquem les columnes a gust
datamsg.replace('', np.nan, inplace=True) #Reemplaçem dades buides per nans

datamsg = datamsg[datamsg['RawData'].str.len() <= 30]
datamsg = datamsg.reset_index(drop=True)

#%% Datetimes

#datamsg = pd.read_csv("datamsg2.csv", header=0, delimiter=';') #En cas que descarreguem un csv de la web i no per API
datasat = pd.read_csv("dataSPP2.csv", header=0, delimiter=';') #Descarreguem la taula amb les dades dels satèl·lits

#Transformem les dates a variables de temps
datamsg['Msg Date'] = pd.to_datetime(datamsg['Msg Date'])

datasat['Start date/time'] = pd.to_datetime(datasat['Start date/time'], format='%d-%m-%Y %H:%M:%S')
datasat['Middle date/time'] = pd.to_datetime(datasat['Middle date/time'], format='%d-%m-%Y %H:%M:%S')
datasat['End date/time'] = pd.to_datetime(datasat['End date/time'], format='%d-%m-%Y %H:%M:%S')

datasat.insert(5, 'Duration_minutes', pd.to_timedelta(datasat['Duration']).dt.total_seconds() / 60.0) #Creem una variable que sigui la duració en minuts com a float

#%% Powers

#Sempre fem servir els mateixos kinéis amb les mateixes potències

power_mapping = {
    217475: 100,
    217089: 250,
    217459: 500,
    217271: 750,
    216875: 1000,
    217124: 1000
}

datamsg['Power'] = datamsg['Platform ID'].map(power_mapping) #Associem un valor de power a cada ID

#%% Antenes

#Per a les proves d'antenes, utilitzarem diferents antenes en cada placa

#Helicoïdal = HA-401H-MSMA
#Llarga = ANT-8WHIP3H-SMA
#Flexible = ANT-433-CW-QW
#Disc = ANT-433-SPS1

antena_mapping = {
    217475: 'HA-401H-MSMA',
    217089: 'HA-401H-MSMA',
    217459: 'HA-401H-MSMA',
    217271: 'HA-401H-MSMA',
    216875: 'HA-401H-MSMA',
    217124: 'HA-401H-MSMA'
}

datamsg['Antena'] = datamsg['Platform ID'].map(antena_mapping) #Assignem un valor string amb l'antena utilitzada a cada ID

#%% Satèl·lits

#Creem diferents dataframes seleccionant només les dades rebudes pel satèl·lit que volem analitzar

MBmsg = datamsg[datamsg['Satellite'] == 'MB']
NKmsg = datamsg[datamsg['Satellite'] == 'NK']
NNmsg = datamsg[datamsg['Satellite'] == 'NN']
MCmsg = datamsg[datamsg['Satellite'] == 'MC']
NPmsg = datamsg[datamsg['Satellite'] == 'NP']
O3msg = datamsg[datamsg['Satellite'] == 'O3']
A1msg = datamsg[datamsg['Satellite'] == 'A1']
SRmsg = datamsg[datamsg['Satellite'] == 'SR']
CSmsg = datamsg[datamsg['Satellite'] == 'CS']
MAmsg = datamsg[datamsg['Satellite'] == 'MA'] #Services not open

#Creem diferents dataframes seleccionant només el satèl·lit que volem analitzar

MBsat = datasat[datasat['Satellite'] == 'MB']
NKsat = datasat[datasat['Satellite'] == 'NK']
NNsat = datasat[datasat['Satellite'] == 'NN']
MCsat = datasat[datasat['Satellite'] == 'MC']
NPsat = datasat[datasat['Satellite'] == 'NP']
O3sat = datasat[datasat['Satellite'] == 'O3']
A1sat = datasat[datasat['Satellite'] == 'A1']
SRsat = datasat[datasat['Satellite'] == 'SR']
CSsat = datasat[datasat['Satellite'] == 'CS']
MAsat = datasat[datasat['Satellite'] == 'MA'] #Services not open

#%% IDs

#Creem diferents dataframes seleccionant només l'ID (placa) que ens interessa analitzar
id217124 = datamsg[datamsg['Platform ID'] == 217124]
id217475 = datamsg[datamsg['Platform ID'] == 217475]
id217089 = datamsg[datamsg['Platform ID'] == 217089]
id217459 = datamsg[datamsg['Platform ID'] == 217459]
id217271 = datamsg[datamsg['Platform ID'] == 217271]
id216875 = datamsg[datamsg['Platform ID'] == 216875]
id217124 = datamsg[datamsg['Platform ID'] == 217124]

#%% Filtres

datasat = datasat.drop(datasat[datasat['Satellite'] == 'MB'].index) #Segons els d'Argos té un mal funcionament
datasat = datasat.drop(datasat[datasat['Satellite'] == 'A1'].index)
datasat = datasat.drop(datasat[datasat['Middle elevation'] <= 30].index) #Eliminem els valors amb una elevació inferior a la que busquem

#%% Correlacions missatges rebuts i enviats

#Comptar missatges enviats
def sended_counter(datatocount):
    
    #Franja de temps a analitzar
    start_date_counter = pd.to_datetime('2024-09-05 00:00:00')
    end_date_counter = pd.to_datetime('2024-09-17 23:59:59')
    datatocount = datatocount[(datatocount['Msg Date'] >= start_date_counter) & (datatocount['Msg Date'] <= end_date_counter)]
    
    if datatocount.empty: #Si no hi ha data, els rebuts són 0
        return 0
    
    listcounter = []
    #Llista dels valors a sumar:
        #Valors més grans que el següent (reinici de counter)
        #Últim valor
    i=-1
    last_valid_counter = 0
    while i < len(datatocount['Counter']):
        i+1
        if pd.isna(datatocount['CRC'].iloc[i]):
            i+=1
            continue
        if pd.isna(datatocount['Counter'].iloc[i]) or datatocount['CRC'].iloc[i]=='N': #Si un valor es un nan o és incorrecte el saltem
            i+=1
            continue
        elif last_valid_counter != 0:
            if last_valid_counter - datatocount['Counter'].iloc[i] > 0:
                listcounter.append(last_valid_counter)
                last_valid_counter = datatocount['Counter'].iloc[i]
            else:
                last_valid_counter = datatocount['Counter'].iloc[i]
        else:
            last_valid_counter = datatocount['Counter'].iloc[i]
        i+=1
    
    if not listcounter:
        listcounter.append(last_valid_counter)
    else:
        if last_valid_counter != listcounter[0]:
            listcounter.append(last_valid_counter)

    print(listcounter)
    reinicis=len(listcounter)-1
    print(f"El comptador s'ha reiniciat {reinicis} cops.")
    enviats = sum(listcounter) #Sumem els comptadors obtinguts i obtenim els enviats totals
    return int(enviats)

#Eliminar missatges repetits (rebuts)
def countmsg(df, column1, column2): #Si el satèl·lit i el missatge coincideixen, és el mateix missatge repetit
    
    #Filtrem la franja horaria a analitzar
    start_date_counter = pd.to_datetime('2024-09-05 00:00:00')
    end_date_counter = pd.to_datetime('2024-09-17 23:59:59')
    df = df[(df['Msg Date'] >= start_date_counter) & (df['Msg Date'] <= end_date_counter)]

    if df.empty: #Si no hi ha data els rebuts són 0
        return 0, 0
    
    # Combine the two columns
    df['combined'] = df[column1].astype(str) + '_' + df[column2]
    
    # Get the number of unique combinations
    received = df['combined'].nunique()
    
    # Filter for rows where CRC is 'Y'
    df_crc_y = df[df['CRC'] == 'Y']
    
    # Get the number of unique combinations where CRC is 'Y'
    received_correct = df_crc_y['combined'].nunique()
    
    return received, received_correct #Obtenim els missatges rebuts totals i els rebuts correctes

#%%
print() 
print("Power = ") #Potència
enviats = sended_counter(id217124) #Missatges enviats    
rebuts, correct_rebuts = countmsg(id217124, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts = round((rebuts / enviats) * 100, 2) if enviats != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts = round((correct_rebuts / enviats) * 100, 2) if enviats != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts} missatges de {enviats}. Èxit: {ratio_rebuts}%")
print(f"Hem rebut {correct_rebuts} missatges correctes de {enviats}. Èxit: {ratio_correct_rebuts}%")

#%%
#Èxit dels powers

#Realitzem un percentatge d'èxit per a cada power (és a dir, per a cada ID) i un de general
#Cal tenir en compte que si hi ha pocs missatges rebuts, segurament els enviats que s'han comptat són erronis
print()
print("Power = 100") #Potència
enviats100 = sended_counter(id217475) #Missatges enviats
rebuts100, correct_rebuts100 = countmsg(id217475, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts100 = round((rebuts100 / enviats100) * 100, 2) if enviats100 != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts100 = round((correct_rebuts100 / enviats100) * 100, 2) if enviats100 != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts100} missatges de {enviats100}. Èxit: {ratio_rebuts100}%")
print(f"Hem rebut {correct_rebuts100} missatges correctes de {enviats100}. Èxit: {ratio_correct_rebuts100}%")

print()
print("Power = 250") #Potència
enviats250 = sended_counter(id217089) #Missatges enviats
rebuts250, correct_rebuts250 = countmsg(id217089, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts250 = round((rebuts250 / enviats250) * 100, 2) if enviats250 != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts250 = round((correct_rebuts250 / enviats250) * 100, 2) if enviats250 != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts250} missatges de {enviats250}. Èxit: {ratio_rebuts250}%")
print(f"Hem rebut {correct_rebuts250} missatges correctes de {enviats250}. Èxit: {ratio_correct_rebuts250}%")

print()
print("Power = 500") #Potència
enviats500 = sended_counter(id217459) #Missatges enviats
rebuts500, correct_rebuts500 = countmsg(id217459, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts500 = round((rebuts500 / enviats500) * 100, 2) if enviats500 != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts500 = round((correct_rebuts500 / enviats500) * 100, 2) if enviats500 != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts500} missatges de {enviats500}. Èxit: {ratio_rebuts500}%")
print(f"Hem rebut {correct_rebuts500} missatges correctes de {enviats500}. Èxit: {ratio_correct_rebuts500}%")

print()
print("Power = 750") #Potència
enviats750 = sended_counter(id217271) #Missatges enviats
rebuts750, correct_rebuts750 = countmsg(id217271, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts750 = round((rebuts750 / enviats750) * 100, 2) if enviats750 != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts750 = round((correct_rebuts750 / enviats750) * 100, 2) if enviats750 != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts750} missatges de {enviats750}. Èxit: {ratio_rebuts750}%")
print(f"Hem rebut {correct_rebuts750} missatges correctes de {enviats750}. Èxit: {ratio_correct_rebuts750}%")

print()
print("Power = 1000") #Potència
enviats1000 = sended_counter(id216875) #Missatges enviats
rebuts1000, correct_rebuts1000 = countmsg(id216875, 'Satellite', 'RawData') #Rebuts i rebuts correctes
ratio_rebuts1000 = round((rebuts1000 / enviats1000) * 100, 2) if enviats1000 != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts1000 = round((correct_rebuts1000 / enviats1000) * 100, 2) if enviats1000 != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts1000} missatges de {enviats1000}. Èxit: {ratio_rebuts1000}%")
print(f"Hem rebut {correct_rebuts1000} missatges correctes de {enviats1000}. Èxit: {ratio_correct_rebuts1000}%")

print()
print("Valors generals") #Potència
enviats = enviats100+enviats250+enviats500+enviats750+enviats1000 #Missatges enviats
rebuts= rebuts100+rebuts250+rebuts500+rebuts750+rebuts1000 #Missatges rebuts
correct_rebuts = correct_rebuts100+correct_rebuts250+correct_rebuts500+correct_rebuts750+correct_rebuts1000 #Missatges rebuts correctes
ratio_rebuts = round((rebuts / enviats) * 100, 2) if enviats != 0 else 0 # Percentatge de rebuts
ratio_correct_rebuts = round((correct_rebuts / enviats) * 100, 2) if enviats != 0 else 0 # Percentatge de rebuts correctes
print(f"Hem rebut {rebuts} missatges de {enviats}. Èxit: {ratio_rebuts}%")
print(f"Hem rebut {correct_rebuts} missatges correctes de {enviats}. Èxit: {ratio_correct_rebuts}%")
    
    #%% Mappings per als plots

#Associem l'èxit a la ID en un mapping
ratio_rebuts=ratio_rebuts
ratio_correct_rebuts=ratio_correct_rebuts
exit_mapping = {
    217475: ratio_correct_rebuts100,
    217089: ratio_correct_rebuts250,
    217459: ratio_correct_rebuts500,
    217271: ratio_correct_rebuts750
    216875: ratio_correct_rebuts1000,
    217124: ratio_correct_rebuts
}

#Associem un color a cada ID (cada ID té una antena i potència concretes)
IDS=[217475,217089,217459,217271,216875,217124]

color_mapping_id = {
    217475: 'blue',
    217089: 'green',
    217459: 'red',
    217271: 'purple',
    216875: 'yellow',
    217124: 'black'
}

#Associem també un color a cada satèl·lit

color_mapping_sat = {
    'MB': '#1f77b4',
    'NK': '#ff7f0e',
    'NN': '#2ca02c',
    'MC': '#d62728',
    'NP': '#9467bd',
    'O3': '#8c564b',
    'A1': '#e377c2',
    'SR': '#7f7f7f',
    'CS': '#bcbd22',
    'MA': '#17becf',
    }
    #%% Gràfics

def plot_satellite_data(msg_df, sat_df, antena_mapping, start_msg_time, end_msg_time, start_sat_time, end_sat_time, IDS):
    
    #Filtrem els missatges erronis
    msg_df = msg_df[msg_df['CRC'] != 'N']

    #Filtrem les dades dins el límit temporal
    msg_data = msg_df[(msg_df['Msg Date'] >= start_msg_time) & (msg_df['Msg Date'] <= end_msg_time)]
    sat_data = sat_df[(sat_df['End date/time'] >= start_sat_time) & (sat_df['Start date/time'] <= end_sat_time)]

    #Limitem el eix temporal del plot
    msg_start = msg_data['Msg Date'].min() - timedelta(minutes=3)
    msg_end = msg_data['Msg Date'].max() + timedelta(minutes=3)
    
    sat_start = sat_data['Start date/time'].min()
    sat_end = sat_data['End date/time'].max()
    
    #Constant de temps per a que les barres tinguin una amplada similar a la seva duració
    time_constant = ((end_sat_time - start_sat_time).total_seconds() / 60)

    #Gràfic de punts (missatges enviats)
    plt.figure(figsize=(12, 6))
    plt.plot(msg_data['Msg Date'], msg_data['Power'], linestyle='', color='gray', alpha=0.5)
    for i, platform_id in enumerate(IDS):
        plt.scatter(msg_data[msg_data['Platform ID'] == platform_id]['Msg Date'], 
                    msg_data[msg_data['Platform ID'] == platform_id]['Power'], 
                    color = color_mapping_id.get(platform_id, 'gray'),  
                    label = f"Antena: {antena_mapping.get(platform_id, 'Unknown')} - Èxit: {exit_mapping.get(platform_id, 'Unknown')}%")
    plt.xlim(msg_start, msg_end)
    plt.ylabel('Power')
    plt.xlabel('Time')
    plt.title(f"Message sendings over time ({ratio_rebuts}%)")
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small', prop={'size': 12})
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(pd.date_range(start=msg_start, end=msg_end, periods=10))
    plt.xticks(rotation=45)
    plt.yticks([1000, 750, 500, 250, 100])
    plt.tight_layout()
    plt.show()
    
    #Gràfic de barres (pas de satèl·lits)
    plt.figure(figsize=(12, 6))
    plt.plot(sat_data['Middle date/time'], sat_data['Middle elevation'], linestyle='', color='gray', alpha=0.5)
    for i, satellite in enumerate(sat_df['Satellite'].unique()):
        satellite_data = sat_df[sat_df['Satellite'] == satellite]
        plt.bar(satellite_data['Middle date/time'],
                satellite_data['Middle elevation'],
                color = color_mapping_sat.get(satellite, 'gray'),
                width = (satellite_data['Duration_minutes']/time_constant)*5,
                label = 'Satellite: ' + satellite, alpha=0.7)
    plt.xlim(sat_start, sat_end)
    plt.ylabel('Elevation')
    plt.xlabel('Time')
    plt.title('Satellite Passes')
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(pd.date_range(start=sat_start, end=sat_end, periods=10))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
    
    #Gràfic general (combinem els missatges enviats amb el pas de satèl·lits)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()

    handles_sat = []
    for i, satellite in enumerate(sat_df['Satellite'].unique()):
        satellite_data = sat_df[sat_df['Satellite'] == satellite]
        ax1.bar(satellite_data['Middle date/time'],
                satellite_data['Middle elevation'],
                color = color_mapping_sat.get(satellite, 'gray'),
                width = (satellite_data['Duration_minutes']/time_constant)*10,
                label = 'Satellite: ' + satellite, alpha=0.7)
        handles_sat.append(Line2D([0], [0], color=color_mapping_sat.get(satellite, 'gray'), lw=4, label='Satellite: ' + satellite))

    scatter_handles = []
    for i, platform_id in enumerate(IDS):
        scatter = ax2.scatter(msg_data[msg_data['Platform ID'] == platform_id]['Msg Date'],
                              msg_data[msg_data['Platform ID'] == platform_id]['Power'],
                              color = color_mapping_id.get(platform_id, 'gray'),
                              label = f"Antena: {antena_mapping.get(platform_id, 'Unknown')} - Èxit: {exit_mapping.get(platform_id, 'Unknown')}%", zorder=3)
        scatter_handles.append(scatter)

    ax2.set_ylabel('Power', color='white')
    ax2.tick_params(axis='y', labelcolor='black')
    ax2.set_yticks([1000, 750, 500, 250, 100])
    ax1.set_ylabel('Elevation', color='black')
    ax1.tick_params(axis='y', labelcolor='black')

    handles = handles_sat + scatter_handles
    plt.xlim(sat_start, sat_end)
    plt.xlabel('Time')
    plt.title(f"Messages sended over satellite passes (General success: {ratio_correct_rebuts}%)")
    plt.legend(handles=handles, loc='center left', bbox_to_anchor=(1.1, 0.5), fontsize='small')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(pd.date_range(start=sat_start, end=sat_end, periods=10))
    ax1.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    plt.show()
    
#Límits temporals
start_msg_time = pd.to_datetime('2024-09-05 00:00:00') #Gràfic de punts i general
end_msg_time = pd.to_datetime('2024-09-17 23:59:59')    
start_sat_time = pd.to_datetime('2024-09-05 00:00:00') #Gràfic de barres
end_sat_time = pd.to_datetime('2024-09-17 23:59:59')

plot_satellite_data(datamsg, datasat, antena_mapping, start_msg_time, end_msg_time, start_sat_time, end_sat_time, IDS)

