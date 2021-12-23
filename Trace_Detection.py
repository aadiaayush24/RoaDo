#!/usr/bin/env python
# coding: utf-8

# In[1]:


import json
import numpy as np
import dateutil.parser
import pandas as pd
from sklearn.metrics.pairwise import haversine_distances
import math
import warnings
warnings.filterwarnings("ignore")


# In[2]:


import csv


# In[3]:


import reverse_geocoder as rg
import folium


# In[4]:


import sys


# In[16]:


class Trace():
    def __init__(self, filepath):
        self.filepath=filepath
        try:
            if(filepath.isnumeric()):
                filepath=f'Trace_db/TraceSplit{filepath}.json'
            with open(filepath, encoding='utf-8') as f:
                data=json.load(f)
        except:
            print("Incorrect file path")
            sys.exit()
        _id=[]
        dt=[]
        try:
            for row in (data['traces']):
                _id.append(row['_id']['$oid'])
                dt.append(dateutil.parser.isoparse(row['timestamp']['$date']))
            self.df=pd.DataFrame(data['traces'])
            
        except:
            for row in (data[0]['traces']):
                _id.append(row['_id']['$oid'])
                dt.append(dateutil.parser.isoparse(row['timestamp']['$date']))
            self.df=pd.DataFrame(data[0]['traces'])
            
        self.df['_id']=_id
        self.df['timestamp']=dt        
        self.df=self.df.sort_values(by='timestamp').reset_index().drop(columns=['index'])
    
    def confirmFirst(self):
        #firstValid=input(f"\nDid you start your journey from {self.df['address'].iloc[0]}?\n Input y for yes, n for no.\n")
        firstValid='n'
        if(firstValid=='y'):
            self.first=3
        elif(firstValid=='n'):
            self.first=1
        else:
            self.first=2
    
    def calcDuration(self):
        duration=[]
        for i in range(len(self.df['timestamp'])):
            if(i==0):
                duration.append(np.nan)
            else:
                duration.append((self.df['timestamp'].loc[i]-self.df['timestamp'].loc[i-1]).seconds)
        self.df['duration']=duration
    
    def calcTravelPossiblity(self):
        def travelPossible(prev_loc, curr_loc, duration):
            max_speed=120
            max_dist_possible_in_duration=duration*120/3600

            #For the inbuilt computation of haversine distance, longitudes and latitudes should be in radians, not degrees
            prev_loc_rad=[math.radians(_) for _ in prev_loc]
            curr_loc_rad=[math.radians(_) for _ in curr_loc]
            aerial_distance=haversine_distances([prev_loc_rad, curr_loc_rad])[0][1]* 6371000/1000

            if(max_dist_possible_in_duration<aerial_distance):
                #IF the aerial distance between the current and the previous location exceeds the maximum distance coverage possible, it is scored the least: 1
                return 1
            else:
                #If the aerial distance between the current and the previous location is zero i.e the same location is being repeated it gets a middle score
                if(aerial_distance==0):
                    return 2
                else:
                    return 4

        coverage_score=[self.first]
        for i in range(1, len(self.df)):
            coverage_score.append(travelPossible(self.df[['latitude', 'longitude']].iloc[i-1], self.df[['latitude', 'longitude']].iloc[i], self.df['duration'].iloc[i]))
        self.df['Travel_Possiblity_Score']=coverage_score
    
    def flagAddress(self):
        address_freq=dict(self.df['address'].value_counts())
        address_valid_score={}
        for i in range(len(self.df)):
            adrs=self.df['address'].iloc[i]

            if(adrs not in address_valid_score.keys()):
                address_valid_score[adrs]=0

            if(self.df['Travel_Possiblity_Score'].iloc[i]==1):
                address_valid_score[adrs]-=1

            elif(self.df['Travel_Possiblity_Score'].iloc[i]==4):
                address_valid_score[adrs]+=1
        address_invalid_score=[key for key, val in address_valid_score.items() if val<0]
        self.df['Flagged_Address']=self.df['address'].apply(lambda x: 0 if x in address_invalid_score else 1)
    
    #def StopScore(self):
        #travelled_from_loc={}
        #for i in range(len(self.df)):    
        #    if(tuple([self.df['latitude'].loc[i], self.df['longitude'].loc[i]]) in travelled_from_loc.keys()):
        #        if(self.df['Travel_Possiblity_Score'].loc[i]==4):
        #            travelled_from_loc[self.df['latitude'].loc[i], self.df['longitude'].loc[i]]=1
        #    else:
        #        travelled_from_loc[tuple([self.df['latitude'].loc[i], self.df['longitude'].loc[i]])]=0
        #
        #stop_score=[]
        #for i in range(len(self.df)):
        #    stop_score.append(travelled_from_loc[tuple([self.df['latitude'].loc[i], self.df['longitude'].loc[i]])])
        #self.df['Stop_Score']=stop_score
    
    def grade(self):
        self.df['Grade']=self.df.apply(lambda row: row.Travel_Possiblity_Score+row.Flagged_Address, axis=1)
        self.df['Rogue_Detected']=self.df['Grade'].apply(lambda x: False if x>2 else True)
    
    def daysTrip(self):
        print(self.df['timestamp'].dt.normalize().value_counts())
     
    def evalRogue(self):
        self.confirmFirst()
        self.calcDuration()
        self.calcTravelPossiblity()
        self.flagAddress()
        self.grade()
        
        error=pd.DataFrame(self.df[self.df['Rogue_Detected']==True])
        
        if('isRouge' in self.df.columns):
            #Detected not rogue by both
            self.i1=len(self.df[(self.df['isRouge']==False) & (self.df['Rogue_Detected']==False)])
            #Detected rogue by both
            self.i2=len(self.df[(self.df['isRouge']==True) & (self.df['Rogue_Detected']==True)])
            #Detected Rogue by in-built algorithm but not by my code
            self.i3=len(self.df[(self.df['isRouge']==True) & (self.df['Rogue_Detected']==False)])
            #Detected Rogue by my code but not by in-built algorithm
            self.i4=len(self.df[(self.df['isRouge']==False) & (self.df['Rogue_Detected']==True)])
            #print("["+str(self.i1)+", "+str(self.i2)+", "+str(self.i3)+", "+str(self.i4)+"]")
        else:
            self.i1=len(self.df['Rogue_Detected']==False)
            self.i2=len(self.df['Rogue_Detected']==True)
            print("["+str(self.i1)+", "+str(self.i2)+"]")
        return error
    
    def correct(self):
        self.df['Corrected']=False
        err_c=[]
        for i in range(1,len(self.df)):
            if(self.df['Rogue_Detected'].iloc[i]==True):
                self.j=i
                self.k=i
                while((self.j<len(self.df)-1) and (self.df['Rogue_Detected'].iloc[self.j]==True)):
                    self.j+=1
                if(self.j==len(self.df)-1 and (self.df['Rogue_Detected'].iloc[self.j]==True)):
                    self.j=i-1
                while((self.k>=0) and (self.df['Rogue_Detected'].iloc[self.k]==True)):
                    self.k-=1
            
                self.x=(self.df['latitude'].iloc[self.j]+self.df['latitude'].iloc[self.k])/2
                self.y=(self.df['longitude'].iloc[self.j]+self.df['longitude'].iloc[self.k])/2
                self.df['timestamp'].iloc[i]=self.df['timestamp'].iloc[self.j]+(self.df['timestamp'].iloc[self.j]-self.df['timestamp'].iloc[self.k])/2
                err_c.append({'Error Latitude': self.df['latitude'].iloc[i], 'Error Longitude': self.df['longitude'].iloc[i], 'Corrected Latitude': self.x, 
                              'Corrected Longitude': self.y, 'File': self.filepath})
                self.df['latitude'].iloc[i]=self.x
                self.df['longitude'].iloc[i]=self.y
                self.df['Corrected'].iloc[i]=True
                self.df['Rogue_Detected'].iloc[i]=False
            
    def mapF(self):
        m=folium.Map(location=[28.1920, 76.6191], zoom_start=7)
        for i in range(len(self.df)):
            if(self.df['Grade'].iloc[i]<3):
                color='red'
            else:
                color='blue'
            folium.Marker([self.df['latitude'].iloc[i], self.df['longitude'].iloc[i]], popup='<strong>'+self.df['address'].iloc[i]+f", {self.df['latitude'].iloc[i]}, {self.df['longitude'].iloc[i]}"+'</strong>', tooltip=self.df['timestamp'].iloc[i], icon=folium.Icon(icon='Cloud', color=color)).add_to(m)
        return m
            
    def mapC(self):
        df=self.df
        m=folium.Map(location=[20.593, 78.962], zoom_start=6)
        for i in range(len(df)):
            if(df['Corrected'].iloc[i]==False):
                color='blue'
            else:
                color='purple'
            folium.Marker([df['latitude'].iloc[i], df['longitude'].iloc[i]], popup='<strong>'+df['address'].iloc[i]+'</strong>', tooltip=df['timestamp'].iloc[i], icon=folium.Icon(icon='Cloud', color=color)).add_to(m)
        return m
    
    


# In[11]:


class TraceFiles():
    
    def __init__(self, start, end):  
        field_names=['Error Latitude', 'Error Longitude', 'Corrected Longitude', 'Corrected Latitude', 'File']
        with open('error_correction.csv', 'w') as f:
                    dictwriter_obj=csv.DictWriter(f, fieldnames=field_names)
                    dictwriter_obj.writeheader()

        for i in range(start, end+1):
            path=str(i)
            file=Trace(path)
            file.evalRogue()
            file.correct()
            print(i)
            #if(i==start):
                #self.error=pd.DataFrame(file.evalRogue())
                #self.error['Table']=i
            #else:
                #curr_error=pd.DataFrame(file.evalRogue())
                #curr_error['Table']=i
                #self.error=self.error.append(curr_error, ignore_index=True)
            
            #print("["+str(file.i1)+", "+str(file.i2)+", "+str(file.i3)+", "+str(file.i4)+"]")


# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:




