#!/usr/bin/env python
import numpy as np

class frame_and_muid(object):
    def __init__(self, frame_id, muid):
        self.frame_id = frame_id
        self.muid = muid

    def __eq__(self, other):
        return (self.frame_id == other.frame_id) and (self.muid == other.muid)

    def __lt__(self, other):
        if(((self.frame_id <= other.frame_id) and (self.muid < other.muid)) or 
           ((self.frame_id < other.frame_id))):
            return True
        else:
            return False
    def __gt__(self, other):
        if(((self.frame_id >= other.frame_id) and (self.muid > other.muid)) or 
           ((self.frame_id > other.frame_id))):
            return True
        else:
            return False

    def __str__(self):
        return f"Frame ID: {self.frame_id}; MUID: {self.muid}"

def populate_dict(dict_name, filename):
    dict_name['filename'] = filename
    dict_name['messages'] = np.loadtxt(filename,delimiter=',',dtype=int,skiprows=1, usecols=(6,7,8,9,10,11,12,13),converters=lambda x: int(x,16))
    dict_name['timestamps'] = np.loadtxt(filename,delimiter=',',dtype=int,skiprows=1, usecols=(0))
    dict_name['ids'] = np.loadtxt(filename,delimiter=',',skiprows=1, dtype=int,usecols=(1),converters=lambda x : int(x,16))
    dict_name['hex_ids'] = np.loadtxt(filename,delimiter=',',dtype=str,skiprows=1, usecols=(1))
    dict_name['hex_messages'] = np.loadtxt(filename,delimiter=',',dtype=str,skiprows=1, usecols=(6,7,8,9,10,11,12,13))

def populate_dict_panda(dict_name, filename):
    dict_name['filename'] = filename
    dict_name['hex_message_block'] = np.loadtxt(filename,delimiter=',',dtype='S16',skiprows=1, usecols=(2), converters=lambda x : x[2:])
    dict_name['hex_messages'] = dict_name['hex_message_block'].view('S2').reshape(dict_name['hex_message_block'].shape[0],8)
    dict_name['hex_ids'] = np.loadtxt(filename,delimiter=',',dtype=str,skiprows=1, usecols=(1))
    v_int = np.vectorize(lambda x: int(x, 16),otypes=[np.uint8])
    dict_name['messages'] = v_int(dict_name['hex_messages'])
    dict_name['ids'] = np.loadtxt(filename,delimiter=',',skiprows=1, dtype=np.uint16,usecols=(1),converters=lambda x : int(x,16))
    dict_name['timestamps'] = np.loadtxt(filename,delimiter=',',dtype=float,skiprows=1, usecols=(4))
    dict_name['bus'] = np.loadtxt(filename,delimiter=',',dtype=np.uint8,skiprows=1, usecols=(0))

def calculate_unique_message_id(dict_name):
    assert dict_name['messages'].shape[1] == 8
    dict_name['messages_unique_ids'] = np.zeros((dict_name['messages'].shape[0],),dtype=np.uint64)
    for i in range(8):
        dict_name['messages_unique_ids'] += dict_name['messages'][:,i].astype(np.uint64)*16**(16-2*(i+1))

def return_all_messages_for_frame(dict_name, frame_id,return_hex=False):
    if(return_hex):
        return dict_name['hex_messages'][np.argwhere(dict_name['ids'] == frame_id)[:,0]]
    else:
        return dict_name['messages'][np.argwhere(dict_name['ids'] == frame_id)[:,0]]

def return_all_frames_messages_for_muid_and_frame(dict_name, frame_id, muid,return_hex=False):
    indices = np.argwhere((dict_name['messages_unique_ids'] == muid)*(dict_name['ids'] == frame_id))[:,0]
    for index in indices:
        if(return_hex):
            return frame_and_muid(dict_name['hex_ids'][index],
                    dict_name['hex_messages'][index])
        else:
            return frame_and_muid(dict_name['ids'][index],
                    dict_name['messages'][index])

def return_unique_messages_for_frame(dict_name, frame_id, return_hex=False):
    messages = []
    unique_muids = np.unique(dict_name['messages_unique_ids'][np.argwhere(dict_name['ids'] == frame_id)[:,0]])
    for unique_muid in unique_muids:
        first_index = np.argwhere((dict_name['messages_unique_ids'] == unique_muid)*(dict_name['ids'] == frame_id))[0,0]
        if(return_hex):
            messages.append(dict_name['hex_messages'][first_index])
        else:
            messages.append(dict_name['messages'][first_index])
    return messages

def return_frame_IDs_with_message_changes(dict_name):
    frame_ids = []
    for frame_id in np.unique(dict_name['ids']):
        unique_muids = np.unique(dict_name['messages_unique_ids'][np.argwhere(dict_name['ids'] == frame_id)[:,0]])
        if(len(unique_muids) > 1):
            frame_ids.append([frame_id,len(unique_muids)])
    return frame_ids

def return_frame_IDs_muids(dict_name, reject_muids = [], bus = None):
    '''
    Return a list of all frame IDs and muids for a log.
    '''
    frames_and_muids = []
    for frame_id in np.unique(dict_name['ids']):
        if(bus):
            unique_muids = np.unique(dict_name['messages_unique_ids'][np.argwhere((dict_name['ids'] == frame_id)*(dict_name['bus'] == bus))[:,0]])
        else:
            unique_muids = np.unique(dict_name['messages_unique_ids'][np.argwhere(dict_name['ids'] == frame_id)[:,0]])
        for unique_muid in unique_muids:
            if(unique_muid not in reject_muids):
                indices = np.argwhere((dict_name['messages_unique_ids'] == unique_muid)*(dict_name['ids'] == frame_id))[:,0]
                frames_and_muids.append(frame_and_muid(frame_id,unique_muid))
    return frames_and_muids

def return_frame_IDs_muids_with_message_changes_in_timestamp_range(dict_name,timestamp_range, reject_muids = [], threshold = 10):
    '''
    This is a search for control signals, rather than physical sensors. Physical sensors can have a nearly infinite number of values.
    '''
    frames_and_muids = []
    for frame_id in np.unique(dict_name['ids']):
        unique_muids = np.unique(dict_name['messages_unique_ids'][np.argwhere(dict_name['ids'] == frame_id)[:,0]])
        if(len(unique_muids) < threshold):
            for unique_muid in unique_muids:
                if(unique_muid not in reject_muids):
                    indices = np.argwhere((dict_name['messages_unique_ids'] == unique_muid)*(dict_name['ids'] == frame_id))[:,0]
                    timestamps = dict_name['timestamps'][indices]
                    if(timestamps[0] > timestamp_range[0] and timestamps[-1] < timestamp_range[-1]):
                        frames_and_muids.append(frame_and_muid(frame_id,unique_muid))
    return frames_and_muids

def return_interesting_timestamps(dict_name,frame_ids):
    timestamps = []
    for frame_id in frame_ids:
        indices = np.argwhere(dict_name['ids'] == frame_id)[:,0]
        if(len(indices)):
            max_diff = np.argmax(np.abs(np.diff(dict_name['messages_unique_ids'][indices])))
            timestamps.append(dict_name['timestamps'][indices][max_diff])
    return timestamps

