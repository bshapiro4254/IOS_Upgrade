
from getpass import getpass
from netmiko import ConnectHandler
from datetime import datetime
from colorama import init
from threading import Thread
from builtins import super    # https://stackoverflow.com/a/30159479
from tqdm import tqdm
from tqdm import trange
import time
import csv
import re
import sys
import logging
import ftplib
import platform
import subprocess
import os
import pysftp

#	###############################################################################################
#	##################### Main functions ##########################################################
#	###############################################################################################
usernm = input("Enter your SSH username: ")
passwd = getpass('Enter SSH Password: ')
ALT_FTPPASS = getpass('Enter FTP Password: ')
current_date = str(datetime.now()).split(' ')[0]
errorLog = open('Cisco_FW_Update_log-{0}.txt'.format(current_date),'a') 


if sys.version_info >= (3, 0):
    _thread_target_key = '_target'
    _thread_args_key = '_args'
    _thread_kwargs_key = '_kwargs'
else:
    _thread_target_key = '_Thread__target'
    _thread_args_key = '_Thread__args'
    _thread_kwargs_key = '_Thread__kwargs'



def main():
    init()
    #FTPSERVER = '10.3.0.244'
    # FTPSERVER = '10.199.168.5'
    FTPSERVER = '10.198.195.60'
    print(Paint_SVAR('Welcome to IOS Upgrade Script.','fg_white','bg_blue'))
    current_date = str(datetime.now()).split(' ')[0]
    username = usernm
    password = passwd
    print(Paint_SVAR('Enter Selected Script Mode.','fg_white','bg_blue'))
    smode = input('Modes: [ Stage (only stage files)| MT_Stage (Stage w/ Multithreading)| Upgrade (upgrade pre-staged devices) | MT_Upgrade (Upgrade w/ MultiThreading)] : ').lower()
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    logger = logging.getLogger("netmiko")
    Device_Thread = {}
    with open('Upgrade_list.csv', newline='') as csvfile:

        reader = csv.DictReader(csvfile, dialect='excel')
        mt_list  = list(reader)
    ftpg_list = mt_list[:]
    full_list = mt_list[:]

    ftp_list = []
    ftp_full = []
    for row in ftpg_list:
        if row['Target_FW_FN'] in ftp_list:
            pass
        else:
            ftp_list.append(row['Target_FW_FN'])
            ftp_full.append(row)
        if row['Target_FWX_FN'] in ftp_list:
            pass
        else:
            ftp_list.append(row['Target_FWX_FN'])
            ftp_full.append(row)
    if smode == 'stage' or smode == 'mt_stage':
        x = 0 
        for row in ftp_full:
            Push_FW_File_to_FTP(FTPSERVER,username,password,row,ftp_list[x])
            x += 1
            pass
    for row in full_list:
        print(Paint_SVAR('{0} {1} {2}'.format(row['LocalIP'], row['LocalVersion'], row['Target_FW_Ver'], row['Target_FW_FN']),'fg_blue','bg_white'))
        if smode == 'mt_upgrade':
            print(Paint_SVAR('Multi-Threaded Upgrade to complete config commands with prestaged images and reboot.','fg_blue','bg_white'))
            break                    

        if smode == 'mt_fsck':
            print(Paint_SVAR('Multi-Threaded Free space check.','fg_blue','bg_white'))
            break                
 
        elif Verify_MD5_Local(row):  
            if smode == 'stage':
                print(Paint_SVAR('Prestaging IOS Images. No config commands will be issued.','fg_blue','bg_white'))
                Image_staging_worker_function(row,username,password,FTPSERVER)
            elif smode == 'mt_stage':
                print(Paint_SVAR('Prestaging IOS Images with MT. No config commands will be issued.','fg_blue','bg_white'))
                break
            elif smode == 'test':
                print(Paint_SVAR('Running Healthcheck test. No config commands will be issued.','fg_blue','bg_white'))
                test_worker_function(row,username,password,FTPSERVER)
            elif smode == 'upgrade':
                print(Paint_SVAR('Using Prestaged images to complete config commands on device and reboot.','fg_blue','bg_white'))
                if device_worker_function(row,username,password,FTPSERVER,True) == True:
                    print(Paint_SVAR('{0} - IOS Update Complete.'.format(row['LocalIP']),'fg_green','bg_white'))
                else:
                    print(Paint_SVAR('{0} - IOS Update Failed.'.format(row['LocalIP']),'fg_red','bg_white'))
            # elif smode == 'full':
            #     print(Paint_SVAR('Script in Full mode. Completing file transfers, config commands and rebooting.','fg_blue','bg_white'))
            #     if device_worker_function(row,username,password,FTPSERVER,False) == True:
            #         print(Paint_SVAR('{0} - IOS Update Complete.'.format(row['LocalIP']),'fg_green','bg_white'))
            #     else:
            #         print(Paint_SVAR('{0} - IOS Update Failed.'.format(row['LocalIP']),'fg_red','bg_white'))
            else:
                print(Paint_SVAR('That is not a valid option.','fg_red','bg_white'))
                sys.exit(1)
        else:
            continue
        if smode != 'mt_upgrade':
            if input('Would you like to continue to the next Device? [y/N] ').upper() in ['Y', 'YES']:
                continue
            else:
                print(Paint_SVAR('Exiting IOS Upgrade Script.','fg_blue','bg_white'))
                break

    if smode == 'mt_stage':
        return_data = {}
        while len(mt_list) > 0:
            mt_short_list = []
            for x in range(0,13):
                mt_short_list.append(mt_list.pop())
                
                if len(mt_list) == 0:
                    break

            for row in mt_short_list:
                Device_Thread[row['LocalIP']] = ThreadWithReturn(target=Image_staging_worker_function, args=(row,username,password,FTPSERVER))
                Device_Thread[row['LocalIP']].start()        
        
            for row in mt_short_list:
                return_data[row['LocalIP']] = Device_Thread[row['LocalIP']].join()
                if return_data[row['LocalIP']] == True:
                    print(Paint_SVAR('{0} - IOS Stage Complete.'.format(row['LocalIP']),'fg_green','bg_white'))
                else:
                    print(Paint_SVAR('{0} - IOS Stage Failed.'.format(row['LocalIP']),'fg_red','bg_white'))        
    
    if smode == 'mt_fsck':
        return_data = {}
        while len(mt_list) > 0:
            mt_short_list = []
            for x in range(0,10):
                mt_short_list.append(mt_list.pop())
                
                if len(mt_list) == 0:
                    break

            for row in mt_short_list:
                Device_Thread[row['LocalIP']] = ThreadWithReturn(target=free_space_list_check_function, args=(row,username,password,FTPSERVER))
                Device_Thread[row['LocalIP']].start()        
        
            for row in mt_short_list:
                return_data[row['LocalIP']] = Device_Thread[row['LocalIP']].join()
                if return_data[row['LocalIP']] == True:
                    print(Paint_SVAR('{0} - Free Space avaialable.'.format(row['LocalIP']),'fg_green','bg_white'))
                else:
                    print(Paint_SVAR('{0} - Free Space not available'.format(row['LocalIP']),'fg_red','bg_white'))        
    
    if smode == 'mt_upgrade':
        return_data = {}
        while len(mt_list) > 0:
            mt_short_list = []
            for x in range(0,25):
                mt_short_list.append(mt_list.pop())
                
                if len(mt_list) == 0:
                    break

            for row in mt_short_list:
                Device_Thread[row['LocalIP']] = ThreadWithReturn(target=device_worker_function, args=(row,username,password,FTPSERVER,True))
                Device_Thread[row['LocalIP']].start()        
        
            for row in mt_short_list:
                return_data[row['LocalIP']] = Device_Thread[row['LocalIP']].join()
                if return_data[row['LocalIP']] == True:
                    print(Paint_SVAR('{0} - IOS Update Complete.'.format(row['LocalIP']),'fg_green','bg_white'))
                else:
                    print(Paint_SVAR('{0} - IOS Update Failed.'.format(row['LocalIP']),'fg_red','bg_white'))        
    errorLog.close()

#	###############################################################################################
#	##################### Worker functions ########################################################
#	###############################################################################################

def free_space_list_check_function(row,username,password,FTPSERVER):
    Image_Push_Results = {}
    net_connect = Connect_Device(row,username,password)
    if net_connect == False:
        net_connect = Connect_Device(row,username,password)
        if net_connect == False:
            return False
    Stack,SMaster = Gen_Stack_List(row,net_connect.send_command_expect('show switch', delay_factor=5))
    row['stack'] = Stack
    Free_Space = Verify_Free_Space(Stack,net_connect,row)
    for switch in Free_Space:
        if switch == False:
            return False
        else:
            continue
    return True
        
def Image_staging_worker_function(row,username,password,FTPSERVER):
    Image_Push_Results = {}
    mixed_stacks = False      
    m_stacks = [] 
    # Push_FW_File_to_FTP(FTPSERVER,username,password,row)
    net_connect = Connect_Device(row,username,password)
    if net_connect == False:
        net_connect = Connect_Device(row,username,password)
        if net_connect == False:
            return False
    Device_Model = net_connect.send_command_expect("show ver", delay_factor=5)
    mixed_stacks = False      
    m_stacks = []             
    if '3650' in Device_Model or '3850' in Device_Model or '3750' in Device_Model:    
        Stack,SMaster = Gen_Stack_List(row,net_connect.send_command_expect('show switch', delay_factor=5))
        full_stack = Stack[:]
        if SMaster == None:
            print(Paint_SVAR('[ {1} - IOS Stage] Firmware copy failed check Stack.'.format(row['LocalIP']),'fg_red','bg_white'))
            SMaster = '1'
            # return False
    else:
        Stack = ['1']
        SMaster = '1'
    if '3650' in Device_Model or '3850' in Device_Model:
        if not Check_Show_Ver_for_BUNDLE(row,Device_Model,Stack):
            print(Paint_SVAR('[ {1} - IOS Stage] 1 or more Stack switches not in bundled mode. Manual intervention required.: {0}'.format(SMaster,row['LocalIP']),'fg_red','bg_white'))
            return False
    if 'ASA' in Device_Model:
        if 'Failover On' in net_connect.send_command_expect("show failover", delay_factor=5):
            row['HA'] = True
            x_count = 2
        else:
            row['HA'] = False
            x_count = 1
    if '3750' in Device_Model:
        Inventory = Parse_Show_Inv(row,net_connect.send_command_expect('show inventory', delay_factor=5))
        # print(Inventory)
        # print(Stack)
        # print(m_stacks)
        for switch, data in Inventory.items():
            if 'X' in data['Desc']:
                print(Paint_SVAR('[ {1} - IOS Stage] Mixed mode stack detected. Using Mixed-Mode Path: {0}'.format(data['Name'],row['LocalIP']),'fg_red','bg_white'))
                mixed_stacks = True
                # print(switch)
                m_stacks.append(data['Name'])
                Stack.remove(data['Name'])
                if SMaster in m_stacks:
                    SMaster = Stack[0]

    row['stack'] = Stack
    row['m_stacks'] = m_stacks
    row['Dev_Type'] = Device_Model
    if 'ASA' in Device_Model:
        Free_Space = Verify_Free_Space(['0'],net_connect,row)
    else:
        Free_Space = Verify_Free_Space(full_stack,net_connect,row)
    Set_Pager = net_connect.send_command_expect("terminal length 0", delay_factor=5)
    try:
        oldfirmware = re.sub('flash:/|flash://|flash:','',re.findall(r'Active-image : (.*)$',net_connect.send_command_expect('show ver'),re.MULTILINE)[0])
    except:
        try:
            oldfirmware = re.sub('flash:/|flash://|flash:','',re.findall(r'System image file is "(.*)"$',net_connect.send_command_expect('show ver'),re.MULTILINE)[0])
        except:
            oldfirmware = 'NA'

    if len(m_stacks) > 0:
        # print(m_stacks)
        # print(Free_Space)
        if 'Freespace_{0}'.format(m_stacks[0]) in Free_Space.keys() == True: 
            print('in mstack push')
            Image_Push_Results['File_Backup_{0}'.format(m_stacks[0])] = True
            print('start push')
            Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{5}:'.format(m_stacks[0],username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],m_stacks[0]),net_connect,'up')
            print('finish push')
            if Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] == True:
                if len(Stack) > 1:
                    for stack_switch in m_stacks:
                        if stack_switch == m_stacks[0]:
                            continue
                        if Stack_File_Copy_Handler(row,'copy flash-{2}:{0} flash-{1}:{0}'.format(row['Target_FW_FN'],stack_switch,m_stacks[0]),net_connect):
                            print(Paint_SVAR('[ {1} - IOS Stage] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                            pass
                        else:
                            print(Paint_SVAR('[ {1} - IOS Stage] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                            return False   
            if Image_Push_Results['File_Backup_{0}'.format(m_stacks[0])] == False or Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] == False:
                msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False
        else:
            # if input('Would you like to Download old image? [N|y]').lower() == 'y':
            #     Image_Push_Results['File_Backup_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format(switch,username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
            # else:
            Image_Push_Results['File_Backup_{0}'.format(m_stacks[0])] = True
            
            
            print(Paint_SVAR('[ {0} - IOS Stage] Not Enough Free Space for image on {0}.'.format(row['LocalIP']),'fg_red','bg_white'))

            print(Paint_SVAR('[ {0} - IOS Stage] Pausing Script to wait for user to perform file clean on device {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
            input('Waiting for file cleanup... Press Enter Once Complete.')
            Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{5}:'.format(m_stacks[0],username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],m_stacks[0]),net_connect,'up')
            if Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] == True:
                if len(m_stacks) > 1:
                    for stack_switch in m_stacks:
                        if stack_switch == m_stacks[0]:
                            continue
                        if Stack_File_Copy_Handler(row,'copy flash-{2}:{0} flash-{1}:{0}'.format(row['Target_FW_FN'],stack_switch,m_stacks[0]),net_connect):
                            print(Paint_SVAR('[ {1} - IOS Stage] Copy of firmware to stack switch : {0} - Completed.'.format(m_stacks[0],row['LocalIP']),'fg_green','bg_white'))
                            pass
                        else:
                            print(Paint_SVAR('[ {1} - IOS Stage] Could not copy firmware to stack switch : {0}'.format(m_stacks[0],row['LocalIP']),'fg_red','bg_white'))
                            return False 
            if Image_Push_Results['File_Backup_{0}'.format(m_stacks[0])] == False or Image_Push_Results['File_Push_{0}'.format(m_stacks[0])] == False:  
                msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False 
                
    if len(Stack) > 1:
        if 'Freespace_{0}'.format(SMaster) in Free_Space.keys():
            if Free_Space['Freespace_{0}'.format(SMaster)] == True:         
                # if input('Would you like to Download old image? [N|y]').lower() == 'y':
                #     Image_Push_Results['File_Backup_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format(switch,username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                # else:
                Image_Push_Results['File_Backup_{0}'.format(SMaster)] = True
                if '3750' in Device_Model:
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{0}:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                if 'ASA' in Device_Model:
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'1')
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],SMaster),net_connect,'2')
                else:
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                if Image_Push_Results['File_Push_{0}'.format(SMaster)] == True:
                    if len(Stack) > 1:
                        for stack_switch in Stack:
                            if stack_switch == SMaster:
                                continue
                            if '3750' in Device_Model:
                                if Stack_File_Copy_Handler(row,'copy flash{2}:{0} flash{1}:{0}'.format(row['Target_FW_FN'],stack_switch,SMaster),net_connect):
                                    print(Paint_SVAR('[ {1} - IOS StageUpdate] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                                    pass
                                else:
                                    print(Paint_SVAR('[ {1} - IOS Stage] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                                    return False   
                            else:
                                if Stack_File_Copy_Handler(row,'copy flash-{2}:{0} flash-{1}:{0}'.format(row['Target_FW_FN'],stack_switch,SMaster),net_connect):
                                    print(Paint_SVAR('[ {1} - IOS Stage] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                                    pass
                                else:
                                    print(Paint_SVAR('[ {1} - IOS Update] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                                    return False                                   
                if Image_Push_Results['File_Backup_{0}'.format(SMaster)] == False or Image_Push_Results['File_Push_{0}'.format(SMaster)] == False:
                    msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                    print(Paint_SVAR(msg,'fg_red','bg_white'))
                    errorLog.write(msg)
                    return False
            else:
                # if input('Would you like to Download old image? [N|y]').lower() == 'y':
                #     Image_Push_Results['File_Backup_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format(switch,username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                # else:
                Image_Push_Results['File_Backup_{0}'.format(SMaster)] = True
                
                
                print(Paint_SVAR('[ {0} - IOS Stage] Not Enough Free Space for image on {0}.'.format(row['LocalIP']),'fg_red','bg_white'))

                print(Paint_SVAR('[ {0} - IOS Stage] Pausing Script to wait for user to perform file clean on device {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                input('Waiting for file cleanup... Press Enter Once Complete.')
                if '3750' in Device_Model:
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{0}:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                elif 'ASA' in Device_Model:                    
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'1')
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],SMaster),net_connect,'2')
                else:
                    Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                if Image_Push_Results['File_Push_{0}'.format(SMaster)] == True:
                    if len(Stack) > 1:
                        for stack_switch in Stack:
                            if stack_switch == SMaster:
                                continue
                            if '3750' in Device_Model:
                                if Stack_File_Copy_Handler(row,'copy flash{2}:{0} flash{1}:{0}'.format(row['Target_FW_FN'],stack_switch,SMaster),net_connect):
                                    print(Paint_SVAR('[ {1} - IOS Stage] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                                    pass
                                else:
                                    print(Paint_SVAR('[ {1} - IOS Stage] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                                    return False   
                            else:
                                if Stack_File_Copy_Handler(row,'copy flash-{2}:{0} flash-{1}:{0}'.format(row['Target_FW_FN'],stack_switch,SMaster),net_connect):
                                    print(Paint_SVAR('[ {1} - IOS Stage] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                                    pass
                                else:
                                    print(Paint_SVAR('[ {1} - IOS Stage] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                                    return False   
                if Image_Push_Results['File_Backup_{0}'.format(SMaster)] == False or Image_Push_Results['File_Push_{0}'.format(SMaster)] == False:  
                    msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                    print(Paint_SVAR(msg,'fg_red','bg_white'))
                    errorLog.write(msg)
                    return False 
        else:
            msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
            print(Paint_SVAR(msg,'fg_red','bg_white'))
            errorLog.write(msg)
            return False           
    else:
        for x in range(0,x_count):
            if x >= 1:
                primary = row['LocalIP']
                row['LocalIP'] = row['StandbyIP']

            if 'Freespace' in Free_Space.keys():
                if Free_Space['Freespace'] == True:
                    # Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,password,FTPSERVER,oldfirmware),net_connect,'down')
                    # Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,password,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                    # if input('Would you like to Download old image? [N|y]').lower() == 'y':
                    #     Image_Push_Results['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                    # else:
                    Image_Push_Results['File_Backup'] = True
                    if '3750' in Device_Model:
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{0}:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                    elif 'ASA' in Device_Model:                    
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'1')
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],SMaster),net_connect,'2')
                    else:
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')                
                    if  Image_Push_Results['File_Push'] == False or  Image_Push_Results['File_Backup'] == False:
                        msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                        print(Paint_SVAR(msg,'fg_red','bg_white'))
                        errorLog.write(msg)
                        return False
                else:
                    # Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,password,FTPSERVER,oldfirmware),net_connect,'down')
                    # Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,password,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                    # if input('Would you like to Download old image? [N|y]').lower() == 'y':
                    #     Image_Push_Results['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                    # else:
                    Image_Push_Results['File_Backup'] = True
                    # Update_Results_Dict['File_Backup'] = True
                    print(Paint_SVAR('[ {0} - IOS Stage] Starting IOS Update. Not Enough Free Space for image on {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                    print(Paint_SVAR('[ {0} - IOS Stage] Pausing Script to wait for user to perform file clean on device {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                    input('Waiting for file cleanup... Press Enter Once Complete.')
                    if '3750' in Device_Model:
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash{0}:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')                
                    elif 'ASA' in Device_Model:                    
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'1')
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} disk0:{4}'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],SMaster),net_connect,'2')
                    else:
                        Image_Push_Results['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(SMaster,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')                
                    if  Image_Push_Results['File_Push'] == False or  Image_Push_Results['File_Backup'] == False:
                        msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                        print(Paint_SVAR(msg,'fg_red','bg_white'))
                        errorLog.write(msg)
                        return False
            if x == x_count - 1:
                row['LocalIP'] = primary
    # try:    
    if Verify_MD5_onDev(net_connect,row,False):
        print(Paint_SVAR('[ {0} - IOS Update] MD5 successful.'.format(row['LocalIP']),'fg_blue','bg_white'))
    if len(Stack) > 1:
        return Image_Push_Results['File_Push_1']    
    else: 
        return Image_Push_Results['File_Push']


def test_worker_function(row,username,password,FTPSERVER):
    net_connect = Connect_Device(row,username,password)
    if net_connect == False:
        return
    Device_Model = net_connect.send_command_expect("show ver", delay_factor=5)
    # print(Device_Model)
    Set_Pager = net_connect.send_command_expect("terminal length 0", delay_factor=5)
    PreCheck = HealthChecks_Function(net_connect,row,Device_Model,'PRE')
    if Check_Dev_Ver(PreCheck,row):
        for section, data in PreCheck['Extracted_Data'].items():
            print(Paint_SVAR(section,'fg_blue','bg_white'))
            print(Paint_SVAR(data,'fg_green','bg_black'))
            wait = input('waiting...')
        PostCheck = HealthChecks_Function(net_connect,row,Device_Model,'POST')
        Compare = ComparePrePost(PreCheck,PostCheck)
        Write_RAW_Report(row['LocalDevice'],PreCheck,'Pre')
        Write_RAW_Report(row['LocalDevice'],PostCheck,'Post')
        Compile_Report(row['LocalDevice'],Compare)
    net_connect.disconnect()

def device_worker_function(row,username,password,FTPSERVER,prestaged):
    if prestaged == False:
        Push_FW_File_to_FTP(FTPSERVER,username,password,row)
    net_connect = Connect_Device(row,username,password)
    if net_connect == False:
        return
    Device_Model = net_connect.send_command_expect("show ver", delay_factor=5)
    context = net_connect.send_command_expect('show mode')
    if 'Security context mode: multiple' in context:
            print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
            net_connect.send_command_expect('changeto system')
    if 'Failover On' in net_connect.send_command_expect("show failover", delay_factor=5):
        print(Paint_SVAR('[ {0} - HA Check ] ASA HA Detected.'.format(row['LocalIP']),'fg_blue','bg_white'))
        row['HA'] = True
        row2 = row.copy()
        row3 = row.copy()
        row2['LocalIP'] = row2['StandbyIP']
        row2['StandbyIP'] = row['LocalIP']
    else:
        row['HA'] = False
    Set_Pager = net_connect.send_command_expect("terminal length 0", delay_factor=5)
    if row['HA'] == False:
        PreCheck = HealthChecks_Function(net_connect,row,Device_Model,'PRE')
        # if input('Print Collected data? [N/y] ').upper() in ['Y','YES']:
        #     for  section, data in PreCheck['Extracted_Data'].items():
        #         print(Paint_SVAR(section,'fg_blue','bg_white'))
        #         print(Paint_SVAR(data,'fg_green','bg_black'))
        #         wait = input('waiting...')
        if Update_IOS_Function(username,password,FTPSERVER,net_connect,row,Device_Model,prestaged):
            if Wait_for_Reboot(row) == True:
                net_connect = Connect_Device(row,username,password)
                count = 0 
                while net_connect == False:
                    count += 1              
                    print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                    time.sleep(30)
                    net_connect = Connect_Device(row,username,password)
                    if count == 5:
                        print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                        return False
                print(Paint_SVAR('[ {0} - Reboot] Waiting 120 seconds for device to stablalize.'.format(row['LocalIP']),'fg_blue','bg_white'))
                try:
                    net_connect.send_command_timing(' \n', delay_factor=5)
                except:
                    print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry.'.format(row['LocalIP']),'fg_yellow','bg_white'))
                    net_connect = Connect_Device(row,username,password)
                    count = 0 
                    while net_connect == False:
                        count += 1              
                        print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                        time.sleep(30)
                        net_connect = Connect_Device(row,username,password)
                        if count == 5:
                            print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                            return False
                    print(Paint_SVAR('[ {0} - Reboot] Waiting 120 seconds for device to stablalize.'.format(row['LocalIP']),'fg_blue','bg_white'))
                time.sleep(120)
                Set_Pager = net_connect.send_command_expect("terminal length 0", delay_factor=5)
                PostCheck = HealthChecks_Function(net_connect,row,Device_Model,'POST')
                Compare = ComparePrePost(PreCheck,PostCheck)
                Write_RAW_Report(row['LocalDevice'],PreCheck,'Pre')
                Write_RAW_Report(row['LocalDevice'],PostCheck,'Post')
                Compile_Report(row['LocalDevice'],Compare)
                net_connect.disconnect()
                return True
            else:
                print(Paint_SVAR('[ {0} - IOS UPDATE] An Error has occured. Review logs for device : {0}'.format(row['LocalIP']),'fg_red','bg_white'))
                return False
    else:
        Fail_Stats = Parse_ASA_Show_Failover(row,net_connect.send_command_expect("show fail state", delay_factor=5))
        PreCheck_pri = HealthChecks_Function(net_connect,row,Device_Model,'PRE')
        # if input('Print Collected data? [N/y] ').upper() in ['Y','YES']:
        #     for  section, data in PreCheck['Extracted_Data'].items():
        #         print(Paint_SVAR(section,'fg_blue','bg_white'))
        #         print(Paint_SVAR(data,'fg_green','bg_black'))
        #         wait = input('waiting...')
        if Fail_Stats['MyState'] == 'Failed' or Fail_Stats['OtState'] == 'Failed':
            print(Paint_SVAR('[ {0} - Upgrade] Device configured for HA but one or more devies in Failed state.'.format(row['LocalIP']),'fg_red','bg_white'))
            return False
        if Fail_Stats['MyState'] != 'Active':
            pass
        else:
            row = row2.copy()
            row2 = row3.copy()

        if Update_IOS_Function(username,password,FTPSERVER,net_connect,row,Device_Model,prestaged):
        
            net_connect = Connect_Device(row,username,password)
            count = 0 
            while net_connect == False:
                count += 1              
                print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                time.sleep(30)
                net_connect = Connect_Device(row,username,password)
                if count == 5:
                    print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                    return False
            print(Paint_SVAR('[ {0} - Reboot] Waiting 120 seconds for device to stablalize.'.format(row['LocalIP']),'fg_blue','bg_white'))
            try:
                net_connect.send_command_timing(' \n', delay_factor=5)
            except:
                print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry.'.format(row['LocalIP']),'fg_yellow','bg_white'))
                net_connect = Connect_Device(row,username,password)
                count = 0 
                while net_connect == False:
                    count += 1              
                    print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                    time.sleep(30)
                    net_connect = Connect_Device(row,username,password)
                    if count == 5:
                        print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                        return False
                print(Paint_SVAR('[ {0} - Reboot] Waiting 120 seconds for device to stablalize.'.format(row['LocalIP']),'fg_blue','bg_white'))
                time.sleep(120)
            net_connect = Connect_Device(row,username,password)
            count = 0 
            while net_connect == False:
                count += 1 
                print(Paint_SVAR('[ {0} - Pri ] Device connect failed. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                time.sleep(30)
                net_connect2 = Connect_Device(row,username,password)
                if count == 5:
                    print(Paint_SVAR('[ {0} - Pri] Device did not connect. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                    return False


            Set_Pager = net_connect.send_command_expect("terminal length 0", delay_factor=5)                    
            PostCheck_pri = HealthChecks_Function(net_connect,row,Device_Model,'POST')
            Compare_pri = ComparePrePost(PreCheck_pri,PostCheck_pri)
            Write_RAW_Report(row['LocalDevice'],PostCheck_pri,'Post')
            Write_RAW_Report(row['LocalDevice'],PreCheck_pri,'Pre')
            Compile_Report(row['LocalDevice'],Compare_pri)
            net_connect.disconnect()
            return True
        else:
            print(Paint_SVAR('[ {0} - IOS UPDATE] An Error has occured. Review logs for device : {0}'.format(row['LocalIP']),'fg_red','bg_white'))
            return False

#	###############################################################################################
#	##################### Device functions #######################################################
#	###############################################################################################


def Connect_Device(row,username,password):
    if 'Port' in row.keys():
        if len(row['Port']) > 0:
            port = int(row['Port'])
        else:
            port = 22
    else:
        port = 22

    cisco_ios = {
        'device_type': 'cisco_ios',
        'ip':   row['LocalIP'],
        'username': username,
        'password': password,
        'port' : port,
        'secret': password,
        'verbose': True
        }

    cisco_nxos = {
        'device_type': 'cisco_nxos',
        'ip':   row['LocalIP'],
        'username': username,
        'password': password,
        'port' : port,
        'secret': password,
        'verbose': True
        }
    
    cisco_asa = {
        'device_type': 'cisco_asa',
        'ip':   row['LocalIP'],
        'username': username,
        'password': password,
        'port' : port,
        'secret': password,
        'verbose': True
        }        

    if "IOS" in row['LocalVersion']:
        try:
            net_connect = ConnectHandler(**cisco_ios)
        except Exception as err:
            errorLog.write('%s , %s connection failed' % (row['LocalDevice'], row['LocalIP']))
            print(Paint_SVAR('Connection Error : %s' % err ,'fg_red','bg_white'))
            return False

    elif "NX-OS" in row['LocalVersion']:
        try:
            net_connect = ConnectHandler(**cisco_nxos)
        except Exception as err:
            errorLog.write('%s , %s connection failed' % (row['LocalDevice'], row['LocalIP']))
            
            print(Paint_SVAR('Connection Error : %s' % err,'fg_red','bg_white'))
            return False

    elif "ASA" in row['LocalVersion']:
        try:
            net_connect = ConnectHandler(**cisco_asa)
        except Exception as err:
            errorLog.write('%s , %s connection failed' % (row['LocalDevice'], row['LocalIP']))
            
            print(Paint_SVAR('Connection Error : %s' % err,'fg_red','bg_white'))
            return False
    try:
        net_connect.enable()
        
        net_connect.send_command_expect('terminal session-timeout 0')
        return net_connect
    except Exception as err:
        errorLog.write('%s , %s enable failed' % (row['LocalDevice'], row['LocalIP']))
        print(Paint_SVAR('Enable Error : %s' % err,'fg_red','bg_white'))
        return False
        
def Wait_for_Reboot(row):
    print(Paint_SVAR('[ {0} - Reboot] Waiting for reboot to complete.'.format(row['LocalIP']),'fg_blue','bg_white'))
    host = row['LocalIP']
    param = '-n' if platform.system().lower()=='windows' else '-c'
    result = 1
    count = 0
    time.sleep(45)
    while result == 1:
        command = ['ping', param, '1', str(host).strip()]
        result = subprocess.call(command,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        count +=1
        if count % 30 == 0:
            print(Paint_SVAR('[ {0} - Reboot] Waiting.'.format(row['LocalIP']),'fg_blue','bg_white'))
        if count > 600:
            result = 'Timeout'
        time.sleep(1)

    if result == 0:
        time.sleep(45)
        print(Paint_SVAR('[ {0} - Reboot] Reboot complete.'.format(row['LocalIP']),'fg_green','bg_white'))
        return True

    elif result == 'Timeout':
        msg = 'Script Timed out waiting for device reboot'
        print(Paint_SVAR(msg,'fg_green','bg_white'))
        errorLog.write(msg)
        return False

def Check_Dev_Ver(PreCheck,row):
    # print(PreCheck['Extracted_Data']['Current_Ver'])
    if float(re.findall(r'^....',PreCheck['Extracted_Data']['Current_Ver'])[0]) >= float(re.findall(r'^....',row['Target_FW_Ver'])[0]):
        # print(Paint_SVAR('[ {0} - PreCheck] Device Firmware is same or newer than target firmware.'.format(row['LocalIP']),'fg_yellow','bg_white'))
        # response = input('Proceed Anyways?...[y|N]')
        # if response.upper() in ['Y', 'YES']:
        return True
        # else:
            # print(Paint_SVAR('[ {0} - PreCheck] Device Firmware is same or newer than target firmware.'.format(row['LocalIP']),'fg_green','bg_white'))
            # return False
    else:
        return True

def Wait_For_Standby(row,net_connect,duration,end):
    time.sleep(30)
    rowz = row.copy()
    rowz['LocalIP'] = rowz['StandbyIP']
    if Wait_for_Reboot(rowz) == True:
        print(Paint_SVAR('[ {0} - Reboot] Waiting 120 seconds for standby to be completely active.'.format(row['LocalIP']),'fg_blue','bg_white'))
        time.sleep(120)
        for x in range(0,end):
            if len(re.findall('Standby Ready',net_connect.send_command_expect('show fail'),re.MULTILINE)) >= 1:
                return True
            else:
                time.sleep(duration)
                continue
    return False

def Push_FW_File_to_FTP(FTPSERVER,username,password,row,FN):
    
# with pysftp.Connection('hostname', username='me', password='secret') as sftp:
#     with sftp.cd('public'):             # temporarily chdir to public
#         sftp.put('/my/local/filename')  # upload file to public/ on remote
#         sftp.get('remote_file')         # get a remote file
    print(Paint_SVAR('[ {2} - FTP] Connecting to FTP Server {0} to stage FW image {1}'.format(FTPSERVER,FN,row['LocalIP']),'fg_blue','bg_white'))
    try:

        # session = ftplib.FTP(FTPSERVER,username,password)
        session = ftplib.FTP(FTPSERVER,username,ALT_FTPPASS)
    
        # cnopts = pysftp.CnOpts()
        # cnopts.hostkeys = None 
        # sftp = pysftp.Connection(FTPSERVER, username=username, password=ALT_FTPPASS,cnopts=cnopts) 
        print(Paint_SVAR(' {0} - [FTP] Connected to FTP Server {0}.'.format(FTPSERVER,row['LocalIP']),'fg_green','bg_white'))
    except Exception as err:
        msg = '[FTP] There was an error connecting to the FTP Server: %s' % err
        print(Paint_SVAR(msg,'fg_red','bg_white'))
        errorLog.write(msg)

    try:        
        print(Paint_SVAR('[ {2} - FTP] Uploading {1} to FTP Server {0}.'.format(FTPSERVER,FN,row['LocalIP']),'fg_blue','bg_white'))
        # with sftp.cd('ftp'):             # temporarily chdir to public
        #     if sftp.exists(row['Target_FW_FN']):
        #         if input('File already present on FTP server. Do you want to overwrite? [N/y]').lower() in ['y','yes']:
        #             sftp.put(row['Target_FW_FN'])  # upload file to public/ on remote
        #         else:
        #             print(Paint_SVAR('[ {2} - FTP] File Exists skipping.'.format(FTPSERVER,row['Target_FW_FN'],row['LocalIP']),'fg_blue','bg_white'))
        if FN in session.nlst():         
            if input('File already present on FTP server. Do you want to overwrite? [N/y]').lower() in ['y','yes']:
                print(Paint_SVAR('[ {2} - FTP] Transfering.'.format(FTPSERVER,FN,row['LocalIP']),'fg_blue','bg_white'))
                file = open(FN,'rb')  # file to send
                filesize = os.path.getsize(FN)
                with tqdm(unit = 'blocks',  unit_scale = True, leave = False, miniters = 1, desc = 'Uploading......', total = filesize) as tqdm_instance:
                    # session.storbinary(f'STOR %s' % row['Target_FW_FN'], file)          # send the file
                    session.storbinary(f'STOR %s' % FN, file, 2048, callback = lambda sent: tqdm_instance.update(len(sent)))
                print(Paint_SVAR('[ {2} - FTP] Upload Completed.'.format(FTPSERVER,FN,row['LocalIP']),'fg_green','bg_white'))
                file.close()                                           # close file and FTP
            else:
                print(Paint_SVAR('[ {2} - FTP] File Exists skipping.'.format(FTPSERVER,FN,row['LocalIP']),'fg_blue','bg_white'))
        else:
            print(Paint_SVAR('[ {2} - FTP] Transfering.'.format(FTPSERVER,FN,row['LocalIP']),'fg_blue','bg_white'))
            file = open(FN,'rb')  # file to send
            filesize = os.path.getsize(FN)
            with tqdm(unit = 'blocks',  unit_scale = True, leave = False, miniters = 1, desc = 'Uploading......', total = filesize) as tqdm_instance:
                # session.storbinary(f'STOR %s' % row['Target_FW_FN'], file)          # send the file
                session.storbinary(f'STOR %s' % FN, file, 2048, callback = lambda sent: tqdm_instance.update(len(sent)))     
        session.quit()                
        
    except:


        msg = '[FTP] There was an error uploading to the FTP Server {0}.'.format(FTPSERVER)
        print(Paint_SVAR(msg,'fg_red','bg_white'))
        errorLog.write(msg)

def Verify_MD5_Local(row):
    command_linux = ['md5sum', row['Target_FW_FN']]
    command_windows = ['.\\fciv.exe ','-md5 ', row['Target_FW_FN']]
    if platform.system().lower()=='windows':
        command = command_windows
        try:
            md5sum = re.sub(r'\\r|\\n','',str(subprocess.check_output(command))).split('//')[3].split(' ')[0]
        except:
            msg = '[{0}] Local file MD5 Checksum command failed.'.format(row['LocalIP'])
            print(Paint_SVAR(msg,'fg_ews','bg_white'))
            errorLog.write(msg)
            return False
    else:
        command = command_linux
        try:
            md5sum = str(subprocess.check_output(command)).split("'")[1].split(' ')[0]
        except:
            msg = '[{0}] Local file MD5 Checksum command failed.'.format(row['LocalIP'])
            
            print(Paint_SVAR(msg,'fg_red','bg_white'))
            errorLog.write(msg)
            return False

    if md5sum.upper() == row['Target_FW_MD5'].upper():
        return True
    else:
        msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
        print(Paint_SVAR(msg,'fg_red','bg_white'))
        errorLog.write(msg)
        return False

def Verify_Free_Space(Stack,net_connect,row):
    Update_Results_Dict = {}
    context = net_connect.send_command_expect('show mode')
    if 'Security context mode: multiple' in context:
        print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
        net_connect.send_command_expect('changeto system')
    if len(Stack) > 1:
        for x in Stack:
            try:
                Update_Results_Dict[x] = re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('dir flash-{0}:'.format(x),delay_factor=5))[0]
            except:
                try:
                    Update_Results_Dict[x] = re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('show flash-{0}:'.format(x),delay_factor=5))[0]
                except:
                    try:
                        Update_Results_Dict[x] = re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('dir flash{0}:'.format(x),delay_factor=5))[0]
                        print(Update_Results_Dict[x])
                    except:
                        try:
                            Update_Results_Dict[x] = re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('show flash{0}:'.format(x),delay_factor=5))[0]
                        except:
                            Update_Results_Dict[x] = 0
            if int(Update_Results_Dict[x]) > int(file_size(row['Target_FW_FN'])):
                Update_Results_Dict['Freespace_{0}'.format(x)] = True
            else:
                Update_Results_Dict['Freespace_{0}'.format(x)] = False
            # print(Update_Results_Dict)
        return Update_Results_Dict
    else:
        try:
            Update_Results_Dict[0]= re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('dir flash:',delay_factor=5))[0]
        except:
            Update_Results_Dict[0]= re.findall(r'\((\d*) bytes free\)',net_connect.send_command_expect('dir',delay_factor=5))[0]
        print(Paint_SVAR('[ {1} - FTP] Free Space - {0}'.format(Update_Results_Dict[0],row['LocalIP']),'fg_blue','bg_white'))
        print(Paint_SVAR('[ {1} - FTP] File Size  - {0}'.format(int(file_size(row['Target_FW_FN'])),row['LocalIP']),'fg_green','bg_white'))
        if int(Update_Results_Dict[0]) > int(file_size(row['Target_FW_FN'])):
            Update_Results_Dict['Freespace'] = True
        else:
            Update_Results_Dict['Freespace'] = False
        return Update_Results_Dict

def Stack_File_Copy_Handler(row,cmd,net_connect):
    timeout_count = 0
    print(Paint_SVAR((cmd),'fg_cyan','bg_black'))
    net_connect.write_channel(cmd + '\n')
    time.sleep(2)
    response = net_connect.read_channel()
    for x in range(0,2):
        # print(response)
        if 'Address or name of remote host' in response or 'Destination filename' in response:
            net_connect.write_channel('\n')
            time.sleep(.25)
            response = net_connect.read_channel()
        elif 'Do you want to over write?' in response:
            net_connect.write_channel('no\n')
            time.sleep(.25)
            response = net_connect.read_channel()
            return True
        else: 
            break
    found = False
    print(Paint_SVAR('[ {0} - Stack Copy] Copying Firmware to Stack Device.'.format(row['LocalIP']),'fg_blue','bg_white'))
    last_count = 0
    stall_count = 0
    while found == False:
        time.sleep(10)
        timeout_count += 10
        response = response + net_connect.read_channel() 
        current_count = len(re.findall('C',response))
        if current_count > last_count:
            last_count = current_count
            stall_count = 0
        else:
            stall_count += 1
            if stall_count > 18:
                print(Paint_SVAR('[ {0} - Stack Copy] Transfer failed. Transfer stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                return False      
            
        # print(response)
        print(Paint_SVAR('[ {1} - Stack Copy] Copying...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
        if 'bytes copied in' in response:    
            print(Paint_SVAR('[ {0} - Stack Copy] Transfer Complete.'.format(row['LocalIP']),'fg_green','bg_white'))
            return True
        elif 'No such file or directory' in response:
            
            print(Paint_SVAR('[ {0} - Stack Copy] Transfer failed. Remote file not found.'.format(row['LocalIP']),'fg_red','bg_white'))
            return False
        elif 'file already existing with this name' in response:
            
            print(Paint_SVAR('[ {0} - Stack Copy] Transfer failed. File Already Exists.'.format(row['LocalIP']),'fg_blue','bg_white'))
            return True 
        elif 'destination path is identical' in response:
            
            print(Paint_SVAR('[ {0} - Stack Copy] Transfer failed. File is already present.'.format(row['LocalIP']),'fg_blue','bg_white'))
            return True            
        if timeout_count > 3600:
            print(Paint_SVAR('[ {0} - Stack Copy] Download Timed out'.format(row['LocalIP']),'fg_red','bg_white'))
            return False

    return False    
       
def FTP_to_DEV_Handler(row,cmd,net_connect,updown):
    timeout_count = 0
    print(Paint_SVAR(cmd,'fg_cyan','bg_black'))
    overwrite = False
    do_over = False
    endloop = False
    md5 = False
    context = net_connect.send_command_expect('show mode')
    if 'Security context mode: multiple' in context:
        print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
        net_connect.send_command_expect('changeto system')
    response = net_connect.send_command_timing(cmd)
    while endloop == False:
        if do_over == True:
           response = net_connect.send_command_timing(cmd)
           do_over = False
        for x in range(0,6):
            if 'Address or name of remote host' in response or 'Destination filename' in response or 'Source username' in response or 'Source filename' in response or 'Source password' in response:
                net_connect.write_channel('\n')
                time.sleep(.25)
                response = net_connect.read_channel()
            elif 'Do you want to over write?' in response:
                print(Paint_SVAR('[ {0} - FTP] PreExisting file detected. Checking MD5'.format(row['LocalIP']),'fg_blue','bg_white'))
                if overwrite == False:
                    net_connect.write_channel('no\n')
                    if updown == '1':
                        MD5 = Verify_MD5_onDev(net_connect,row,False)
                    if updown == '2':
                        MD5 = Verify_MD5_onDev(net_connect,row,True)
                    if MD5 == True:
                        print(Paint_SVAR('[ {0} - FTP] File Passed MD5. Continuing.'.format(row['LocalIP']),'fg_blue','bg_white'))
                        return True
                    # if input('Do you want to Overwrite[y|N] : ').lower() in  ['y','yes']:
                    else:
                        do_over = True
                        overwrite = True
                else:
                    print(Paint_SVAR('[ {0} - FTP] File Faied MD5. Overwriting.'.format(row['LocalIP']),'fg_blue','bg_white'))
                    if 'ASA' in row['Dev_Type']:
                        net_connect.write_channel('y\n')
                    else:
                        net_connect.write_channel('confirm\n')
                    endloop = True
            else:
                endloop = True
    
    found = False
    print(Paint_SVAR('[ {0} - FTP] Uploading new Firmware to device.'.format(row['LocalIP']),'fg_blue','bg_white'))
    last_count = 0
    stall_count = 0
    while found == False:
        time.sleep(30)
        timeout_count += 30
        response = response + net_connect.read_channel() 
        print(response)
        current_count = len(re.findall('!',response))
        if current_count > last_count:
            last_count = current_count
            stall_count = 0
        else:
            stall_count += 1
            if stall_count > 15:
                print(Paint_SVAR('[ {0} - FTP] Transfer failed. Transfer stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                return False      
            
        # print(response)
        print(Paint_SVAR('[ {1} - FTP] Transfering...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
        if 'bytes copied in' in response:    
            print(Paint_SVAR('[FTP] Transfer Complete.','fg_green','bg_white'))
            return True
        elif 'No such file or directory' in response :
            
            print(Paint_SVAR('[ {0} - FTP] Transfer failed. Remote file not found.'.format(row['LocalIP']),'fg_red','bg_white'))
            return False
        elif 'Permission denied' in response : 
            print(Paint_SVAR('[ {0} - FTP] Transfer failed. Permission denied.'.format(row['LocalIP']),'fg_red','bg_white'))
            return False
        if timeout_count > 12000:
            print(Paint_SVAR('[ {0} - FTP] Download Timed out'.format(row['LocalIP']),'fg_red','bg_white'))
            return False

    return False
    
def Verify_MD5_onDev(net_connect,row,first):
    Update_Results_Dict = {}
    print(Paint_SVAR('[ {0} - MD5] Verifying MD5 Hash for New FW Image.'.format(row['LocalIP']),'fg_blue','bg_white'))
    timeout_count = 0
    if 'ASA' in row['Dev_Type']:
        stall_count = 0
        last_count = 0
        current_count = 0
        print(Paint_SVAR('[ {0} - MD5] Confirming MD5 Hash on switch.'.format(row['LocalIP']),'fg_blue','bg_white'))
        Update_Results_Dict['MD5'] = ''
        if first == False:
            net_connect.write_channel('    verify /md5 disk0:{0}\n'.format(row['Target_FW_FN']))
        else:
            net_connect.write_channel('    verify /md5 disk0:{0}\n'.format(row['Target_FWX_FN']))
        found = False
        while found == False:
            time.sleep(10)
            timeout_count += 10
            # print(Update_Results_Dict['MD5'])
            print(Paint_SVAR('[ {1} - MD5] Checking...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['MD5'] = Update_Results_Dict['MD5'] + net_connect.read_channel() 
            print (Update_Results_Dict['MD5'])
            current_count = len(re.findall('.',Update_Results_Dict['MD5']))
            if 'Done!' in Update_Results_Dict['MD5']:
                break 
            if '(No such file or directory)' in Update_Results_Dict['MD5']:
                print(Paint_SVAR('[ {0} - MD5] File not present. Re-Run Stage.'.format(row['LocalIP']),'fg_red','bg_white'))
                return False
            elif current_count > last_count:
                last_count = current_count
                stall_count = 0
             
            else:
                stall_count += 1
                if stall_count > 6:
                    print(Paint_SVAR('[ {0} - MD5] Check failed. Check stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                    return False  

        md5sum = re.findall(r' = (.*?)\s',Update_Results_Dict['MD5'],re.MULTILINE)[0]                
        if first == False:
            if md5sum.upper() == row['Target_FW_MD5'].upper():
                print(Paint_SVAR('[ {0} - MD5] Hash Match Confirmed.'.format(row['LocalIP']),'fg_green','bg_white'))
                return True
            else:
                msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False 
        else:
            if md5sum.upper() == row['Target_FWX_MD5'].upper():
                print(Paint_SVAR('[ {0} - MD5] Hash Match Confirmed.'.format(row['LocalIP']),'fg_green','bg_white'))
                return True
            else:
                msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False 
    elif len(row['stack']) > 1 and first == False:
        if len(row['m_stacks']) >= 1:
            for x in row['m_stacks']:
                stall_count = 0
                last_count = 0
                current_count = 0
                print(Paint_SVAR('[ {1} - MD5] Confirming MD5 Hash on switch {0}.'.format(x,row['LocalIP']),'fg_blue','bg_white'))
                print(Paint_SVAR('verify /md5 flash{0}:{1}'.format(x,row['Target_FWX_FN']),'fg_cyan','bg_black'))
                Update_Results_Dict['MD5_{0}'.format(x)] = ''
                net_connect.write_channel('    verify /md5 flash{0}:{1}\n'.format(x,row['Target_FWX_FN']))    
                found = False
                while found == False:
                    time.sleep(10)
                    timeout_count += 10
                    # print(Update_Results_Dict['MD5_{0}'.format(x)] )
                    print(Paint_SVAR('[ {1} - MD5] Checking...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
                    Update_Results_Dict['MD5_{0}'.format(x)] = Update_Results_Dict['MD5_{0}'.format(x)] + net_connect.read_channel() 
                    current_count = len(re.findall('.',Update_Results_Dict['MD5_{0}'.format(x)]))
                    if 'Done!' in Update_Results_Dict['MD5_{0}'.format(x)]:
                        break
                    if '(No such file or directory)' in Update_Results_Dict['MD5_{0}'.format(x)]:
                        print(Paint_SVAR('[ {0} - MD5] File not present. Re-Run Stage.'.format(row['LocalIP']),'fg_red','bg_white'))
                        return False
                    elif current_count > last_count:
                        last_count = current_count
                        stall_count = 0
                    else:
                        stall_count += 1
                        if stall_count > 100:
                            print(Paint_SVAR('[ {0} - MD5] Check failed. Check stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                            return False   
                
            
            md5sum = re.findall(r' = (.*?)\s',Update_Results_Dict['MD5_{0}'.format(x)])[0]
            if md5sum.upper() == row['Target_FWX_MD5'].upper():
                print(Paint_SVAR('[ {0} - MD5] Hash Match Confirmed.'.format(row['LocalIP']),'fg_green','bg_white'))
                return True
            else:
                msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False    
        for x in row['stack']:
            stall_count = 0
            last_count = 0
            current_count = 0
            print(Paint_SVAR('[ {1} - MD5] Confirming MD5 Hash on switch {0}.'.format(x,row['LocalIP']),'fg_blue','bg_white'))
            print(Paint_SVAR('verify /md5 flash-{0}:{1}'.format(x,row['Target_FW_FN']),'fg_cyan','bg_black'))
            Update_Results_Dict['MD5_{0}'.format(x)] = ''
            net_connect.write_channel('    verify /md5 flash-{0}:{1}\n'.format(x,row['Target_FW_FN']))    
            found = False
            while found == False:
                time.sleep(10)
                timeout_count += 10
                # print(Update_Results_Dict['MD5_{0}'.format(x)] )
                print(Paint_SVAR('[ {1} - MD5] Checking...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
                Update_Results_Dict['MD5_{0}'.format(x)] = Update_Results_Dict['MD5_{0}'.format(x)] + net_connect.read_channel() 
                current_count = len(re.findall('.',Update_Results_Dict['MD5_{0}'.format(x)]))
                if 'Done!' in Update_Results_Dict['MD5_{0}'.format(x)]:
                    break
                if '(No such file or directory)' in Update_Results_Dict['MD5_{0}'.format(x)]:
                    print(Paint_SVAR('[ {0} - MD5] File not present. Re-Run Stage.'.format(row['LocalIP']),'fg_red','bg_white'))
                    return False
                elif current_count > last_count:
                    last_count = current_count
                    stall_count = 0
                else:
                    stall_count += 1
                    if stall_count > 100:
                        print(Paint_SVAR('[ {0} - MD5] Check failed. Check stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                        return False   
            
            md5sum = re.findall(r' = (.*?)\s',Update_Results_Dict['MD5_{0}'.format(x)])[0]
            if md5sum.upper() == row['Target_FW_MD5'].upper():
                print(Paint_SVAR('[ {0} - MD5] Hash Match Confirmed.'.format(row['LocalIP']),'fg_green','bg_white'))
                pass
            else:
                msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
                print(Paint_SVAR(msg,'fg_red','bg_white'))
                errorLog.write(msg)
                return False 
        return True
    else:
        stall_count = 0
        last_count = 0
        current_count = 0
        print(Paint_SVAR('[ {0} - MD5] Confirming MD5 Hash on switch.'.format(row['LocalIP']),'fg_blue','bg_white'))
        Update_Results_Dict['MD5'] = ''
        net_connect.write_channel('    verify /md5 flash:{0}\n'.format(row['Target_FW_FN']))    
        found = False
        while found == False:
            time.sleep(10)
            timeout_count += 10
            # print(Update_Results_Dict['MD5'])
            print(Paint_SVAR('[ {1} - MD5] Checking...[{0}]'.format(current_count,row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['MD5'] = Update_Results_Dict['MD5'] + net_connect.read_channel() 
            current_count = len(re.findall('.',Update_Results_Dict['MD5']))
            if 'Done!' in Update_Results_Dict['MD5']:
                break 
            if '(No such file or directory)' in Update_Results_Dict['MD5']:
                print(Paint_SVAR('[ {0} - MD5] File not present. Re-Run Stage.'.format(row['LocalIP']),'fg_red','bg_white'))
                return False
            elif current_count > last_count:
                last_count = current_count
                stall_count = 0
             
            else:
                stall_count += 1
                if stall_count > 6:
                    print(Paint_SVAR('[ {0} - MD5] Check failed. Check stalled.'.format(row['LocalIP']),'fg_red','bg_white'))
                    return False  

        md5sum = re.findall(r' = (.*?)\s',Update_Results_Dict['MD5'])[0]                
        if md5sum.upper() == row['Target_FW_MD5'].upper():
            print(Paint_SVAR('[ {0} - MD5] Hash Match Confirmed.'.format(row['LocalIP']),'fg_green','bg_white'))
            return True
        else:
            msg = '[{0}] Local file MD5 Checksum does not match set value.'.format(row['LocalIP'])
            print(Paint_SVAR(msg,'fg_red','bg_white'))
            errorLog.write(msg)
            return False 
    return True

#	###############################################################################################
#	##################### IOS Upgrade functions ###################################################
#	###############################################################################################


def Update_IOS_Function(username,password,FTPSERVER,net_connect,row,Device_Model,prestaged):
    print(Paint_SVAR('[ {0} - IOS Update] Starting IOS Update.'.format(row['LocalIP']),'fg_blue','bg_white'))
    Update_Results_Dict = {}
    if 'ASA' in Device_Model and row['StandbyIP'] != 'None':
        row2 = row.copy()
        row3 = row.copy()
        row2['LocalIP'] = row2['StandbyIP']
        row2['StandbyIP'] = row['LocalIP']
        context = net_connect.send_command_expect('show mode')
        if 'Security context mode: multiple' in context:
            net_connect.send_command_expect('changeto mode admin')
        failover = net_connect.send_command_expect("show failover", delay_factor=5)
        if 'Failover On' in failover:
            if 'This host: Primary - Active' in failover:
                pass
            else:
                row = row2.copy()
                row2 = row3.copy()
                print(Paint_SVAR('[ {0} - IOS Update] Switching to HA Master.'.format(row['LocalIP']),'fg_blue','bg_white'))
                net_connect = Connect_Device(row,username,password)
                count = 0 
                while net_connect == False:
                    count += 1              
                    print(Paint_SVAR('[ {0} - Reboot] Device connect failed after standby reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                    time.sleep(30)
                    net_connect = Connect_Device(row,username,password)
                    if count == 5:
                        print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                        return False
            row['HA'] = True
            row2['HA'] = True
        else:
            row['HA'] = False

    else:
        row['HA'] = False  
    context = net_connect.send_command_expect('show mode')
    if 'Security context mode: multiple' in context:
        net_connect.send_command_expect('changeto system') 

    mixed_stacks = False      
    m_stacks = []             
    if '3650' in Device_Model or '3850' in Device_Model or '3750' in Device_Model:    
        Stack,SMaster = Gen_Stack_List(row,net_connect.send_command_expect('show switch', delay_factor=5))
        if SMaster == None:
            print(Paint_SVAR('[ {1} - IOS Update] Firmware copy failed check Stack.'.format(row['LocalIP']),'fg_red','bg_white'))
            SMaster = '1'
            # return False
    else:
        Stack = ['1']
        SMaster = '1'     
    if '3750' in Device_Model:
        Inventory = Parse_Show_Inv(row,net_connect.send_command_expect('show inventory', delay_factor=5))
        # print(Inventory)
        # print(Stack)
        # print(m_stacks)
        for switch, data in Inventory.items():
            if 'X' in data['Desc']:
                print(Paint_SVAR('[ {1} - IOS Update] Mixed mode stack detected. Using Mixed-Mode Path: {0}'.format(data['Name'],row['LocalIP']),'fg_red','bg_white'))
                mixed_stacks = True
                # print(switch)
                m_stacks.append(data['Name'])
                Stack.remove(data['Name'])
                if SMaster in m_stacks:
                    SMaster = Stack[0]
    if 'ASA' in Device_Model:
        if 'Failover On' in net_connect.send_command_expect("show failover", delay_factor=5):
            row['HA'] = True
        else:
            row['HA'] = False
        context = net_connect.send_command_expect('show mode')
        if 'Security context mode: multiple' in context:
            net_connect.send_command_expect('changeto mode admin')            
    row['stack'] = Stack
    row['m_stacks'] = m_stacks
    row['Dev_Type'] = Device_Model
    try:
        oldfirmware = re.sub('flash:/|flash://|flash:','',re.findall(r'Active-image : (.*)$',net_connect.send_command_expect('show ver'),re.MULTILINE)[0])
    except:
        try:
            oldfirmware = re.sub('flash:/|flash://|flash:','',re.findall(r'System image file is "(.*)"$',net_connect.send_command_expect('show ver'),re.MULTILINE)[0])
        except:
            oldfirmware = 'NA'
    if prestaged == False:
        Free_Space = Verify_Free_Space(Stack,net_connect,row)          
        if len(m_stacks) > 0:
            if 'Freespace_{0}'.format(m_stacks[0]) in Free_Space.keys() == True: 
                Image_Push_Results['File_Backup_{0}'.format(SMaster)] = True
                Image_Push_Results['File_Push_{0}'.format(SMaster)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(m_stacks[0],username,ALT_FTPPASS,FTPSERVER,row['Target_FWX_FN'],m_stacks[0]),net_connect,'up')
                if Image_Push_Results['File_Push_{0}'.format(SMaster)] == True:
                    if len(Stack) > 1:
                        for stack_switch in m_stacks:
                            if stack_switch == m_stacks[0]:
                                continue
                            if Stack_File_Copy_Handler(row,'copy flash-{2}:{0} flash-{1}:{0}'.format(row['Target_FW_FN'],stack_switch,m_stacks[0]),net_connect):
                                print(Paint_SVAR('[ {1} - IOS Update] Copy of firmware to stack switch : {0} - Completed.'.format(stack_switch,row['LocalIP']),'fg_green','bg_white'))
                                pass
                            else:
                                print(Paint_SVAR('[ {1} - IOS Update] Could not copy firmware to stack switch.  : {0}'.format(stack_switch,row['LocalIP']),'fg_red','bg_white'))
                                return False   
                if Image_Push_Results['File_Backup_{0}'.format(SMaster)] == False or Image_Push_Results['File_Push_{0}'.format(SMaster)] == False:
                    msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                    print(Paint_SVAR(msg,'fg_red','bg_white'))
                    errorLog.write(msg)
                    return False

        if len(Stack) > 1:
            for switch in Stack:
                switch = re.sub(r'\*','',switch).strip()

                Free_Space = Verify_Free_Space(Stack,net_connect,row)
                if Free_Space['Freespace_{0}'.format(switch)] == True:
                    # if input('Would you like to Download old image? [N|y]').lower() == 'y':
                    #     Update_Results_Dict['File_Backup_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy flash{0}:{4} ftp://{1}:{2}@{3}'.format(switch,username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                    # else:
                    Update_Results_Dict['File_Backup_{0}'.format(switch)] = True
                    Update_Results_Dict['File_Push_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(switch,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')
                 
                    if Update_Results_Dict['File_Backup_{0}'.format(switch)] == False or Update_Results_Dict['File_Push_{0}'.format(switch)] == False:
                        msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                        print(Paint_SVAR(msg,'fg_red','bg_white'))
                        errorLog.write(msg)
                        return False
                else:
                    # Update_Results_Dict['File_Backup_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy flash{0}:{4} ftp://{1}:{2}@{3}'.format(switch,username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                    Update_Results_Dict['File_Backup_{0}'.format(switch)] = True

                    print(Paint_SVAR('[ {0} - IOS Update] Starting IOS Update. Not Enough Free Space for image on {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                    print(Paint_SVAR('[ {0} - IOS Update] Pausing Script to wait for user to perform file clean on device {0}.'.format(row['LocalIP']),'fg_red','bg_white'))               
                    input('Waiting for file cleanup... Press Enter Once Complete.')
                    Update_Results_Dict['File_Push_{0}'.format(switch)] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format(switch,username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN'],SMaster),net_connect,'up')                
                 
                    if Update_Results_Dict['File_Backup_{0}'.format(switch)] == False or Update_Results_Dict['File_Push_{0}'.format(switch)] == False:
                        msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                        print(Paint_SVAR(msg,'fg_red','bg_white'))
                        errorLog.write(msg)
                        return False                
        else:
            if Free_Space['Freespace'] == True:
                # Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,password,FTPSERVER,oldfirmware),net_connect,'down')
                # Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,password,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                # if input('Would you like to Download old image? [N|y]').lower() == 'y':                
                #     Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                # else:
                Update_Results_Dict['File_Backup'] = True
                Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                if  Update_Results_Dict['File_Push'] == False or  Update_Results_Dict['File_Backup'] == False:
                    msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                    print(Paint_SVAR(msg,'fg_red','bg_white'))
                    errorLog.write(msg)
                    return False
            else:
                # Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,password,FTPSERVER,oldfirmware),net_connect,'down')
                # Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,password,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                if input('Would you like to Download old image? [N|y]').lower() == 'y':
                    Update_Results_Dict['File_Backup'] = FTP_to_DEV_Handler(row,'copy flash:{4} ftp://{1}:{2}@{3}'.format('null',username,ALT_FTPPASS,FTPSERVER,oldfirmware),net_connect,'down')
                else:
                    Update_Results_Dict['File_Backup'] = True
                
                print(Paint_SVAR('[ {0} - IOS Update] Starting IOS Update. Not Enough Free Space for image on {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                print(Paint_SVAR('[ {0} - IOS Update] Pausing Script to wait for user to perform file clean on device {0}.'.format(row['LocalIP']),'fg_red','bg_white'))
                input('Waiting for file cleanup... Press Enter Once Complete.')
                Update_Results_Dict['File_Push'] = FTP_to_DEV_Handler(row,'copy ftp://{1}:{2}@{3}/{4} flash:'.format('null',username,ALT_FTPPASS,FTPSERVER,row['Target_FW_FN']),net_connect,'up')
                if  Update_Results_Dict['File_Push'] == False or  Update_Results_Dict['File_Backup'] == False:
                    msg = '[{0}] One or More file transfers to device failed for : {0}.'.format(row['LocalIP'])
                    print(Paint_SVAR(msg,'fg_red','bg_white'))
                    errorLog.write(msg)
                    return False

        # try:    
    if Verify_MD5_onDev(net_connect,row,False):
        print(Paint_SVAR('[ {0} - IOS Update] MD5 successful. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
        if '3650' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 3650 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            if not Check_Show_Ver_for_BUNDLE(row,Device_Model,Stack):
                print(Paint_SVAR('[ {1} - IOS Update] 1 or more Stack switches not in bundled mode. Manual inervention required.: {0}'.format(SMaster,row['LocalIP']),'fg_red','bg_white'))
                return False
            Update_Results_Dict['Dev_Type'] = '3650'
            boot_vars = re.findall(r'boot system switch all flash.*',net_connect.send_command_expect('sh run | i boot',delay_factor=5))
            old_boot_vars = []
            for var in boot_vars:
                if row['Target_FW_FN'] in var:
                    pass
                else:
                    old_boot_vars.append(var)
            for var in old_boot_vars:
                Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['conf t','no ' + var],delay_factor=5)    
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['conf t','boot system switch all flash:{0}'.format(row['Target_FW_FN'])],delay_factor=5)

        if '3750' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 3750 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '3750'
            if len(m_stacks) > 0:
                for switch_n1 in Stack:
                    Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('boot system switch {0} flash:{1}'.format(switch_n1,row['Target_FW_FN']),delay_factor=5)
                for switch_n2 in Stack:
                    Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('boot system switch {0} flash:{1}'.format(switch_n2,row['Target_FWX_FN']),delay_factor=5)
            else:
                Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('boot system switch all flash:{0}'.format(row['Target_FW_FN']),delay_factor=5)

        elif '3850' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 3850 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            if not Check_Show_Ver_for_BUNDLE(row,Device_Model,Stack):
                print(Paint_SVAR('[ {1} - IOS Update] 1 or more Stack switches not in bundled mode. Manual inervention required.: {0}'.format(SMaster,row['LocalIP']),'fg_red','bg_white'))
                return False
            Update_Results_Dict['Dev_Type'] = '3850'
            #<Match version number and switch between commands>
            if int(version.split('.')[0]) < 16:

                Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('software install file flash:{0} new force'.format(row['Target_FW_FN']),delay_factor=5)
            else:
                Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('request platform software package install switch all file flash:{0}'.format(row['Target_FW_FN']),delay_factor=5)

        elif '4500-noVSS' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 4500 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '4500-noVSS'
            Update_Results_Dict['Slave_Copy'] = net_connect.send_command_expect('copy bootflash:{0} slavebootflash:'.format(row['Target_FW_FN']),delay_factor=5)
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['boot system flash bootflash:{0}'.format(row['Target_FW_FN']),'no boot system flash bootflash:{0}'.format(row['Old_FW_FN']),'exit'],delay_factor=5)

        elif '4500' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 4500 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '4500'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['boot system flash bootflash:{0}'.format(row['Target_FW_FN']),'no boot system flash bootflash:{0}'.format(row['Old_FW_FN']),'exit'],delay_factor=5)
                
        elif '4500-x VSS' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 4500 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '4500-x VSS'
            Update_Results_Dict['Slave_Copy'] = net_connect.send_command_expect('copy bootflash:{0} slavebootflash:{0}'.format(row['Target_FW_FN']),delay_factor=5)
            Update_Results_Dict['Slave_Copy_RMON'] = net_connect.send_command_expect('copy bootflash:{0} slavebootflash:{0}'.format(row['Target_RMON_FN']),delay_factor=5)
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['no boot system flash bootflash:{0}'.format(row['Old_FW_FN']),'boot system flash bootflash:{0}'.format(row['Target_FW_FN']),'boot system flash bootflash:{0}'.format(row['Target_RMON_FN']),'exit'],delay_factor=5)

        elif '4506' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 4506 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '4506'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['no boot system flash bootflash:{0}'.format(row['Old_FW_FN']),'boot system flash bootflash:{0}'.format(row['Target_FW_FN']),'boot system flash bootflash:{0}'.format(row['Target_RMON_FN']),'config-register 0x2102','exit'],delay_factor=5)

        elif 'C4510R' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] C4510R Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = 'C4510R'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['no boot system bootflash:{0}'.format(row['Old_FW_FN']),'boot system bootflash:{0}'.format(row['Target_FW_FN']),'boot system bootflash:{0}'.format(row['Target_RMON_FN']),'config-register 0x2102','exit'],delay_factor=5)

        elif 'IE' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] IE Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = 'IE'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['boot system flash:{0}'.format(row['Target_FW_FN'])],delay_factor=5)

        elif '9300' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 9300 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '9300'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['boot system flash:packages.conf','exit'],delay_factor=5)
            Update_Results_Dict['Package_install'] = net_connect.send_command_expect('install add file flash:{0} activate commit'.format(row['Target_FW_FN']),delay_factor=5)

        elif '9400' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 9400 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '9400'
            Update_Results_Dict['Boot_CMD'] = net_connect.send_config_set(['config t'',boot system bootflash:packages.conf','exit'],delay_factor=5)
            Update_Results_Dict['Package_install'] = net_connect.send_command_expect('install add file bootflash:{0} activate commit'.format(row['Target_FW_FN']),delay_factor=5)

        elif '9500' in Device_Model:
            print(Paint_SVAR('[ {0} - IOS Update] 9500 Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = '9500'
            Update_Results_Dict['Package_install'] = net_connect.send_command_expect('install add file flash:{0} activate commit'.format(row['Target_FW_FN']),delay_factor=5)
            Update_Results_Dict['Boot_CMD'] = net_connect.send_command_expect('boot flash:packages.conf',delay_factor=5)
        
        elif 'ASA' in Device_Model:
            context = net_connect.send_command_expect('show mode')
            if 'Security context mode: multiple' in context:
                print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
                net_connect.send_command_expect('changeto system')
            remove_boot_cmd = ['conf t']
            Current_Boot = net_connect.send_command_expect('show running-config boot system',delay_factor=5)
            for line in Current_Boot.split('\n'):
                remove_boot_cmd.append('no ' + line)
            remove_boot_cmd.append('exit')
            print(Paint_SVAR('[ {0} - IOS Update] ASA Detected. Removing old Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))    
            Update_Results_Dict['Boot_CMD1'] = net_connect.send_config_set(remove_boot_cmd,delay_factor=5)
            print(Paint_SVAR('[ {0} - IOS Update] ASA Detected. Issuing Boot Commands.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Dev_Type'] = 'ASA'
            Update_Results_Dict['Boot_CMD1'] = net_connect.send_config_set(['config t','boot system disk0:/{0}'.format(row['Target_FW_FN']),'exit'],delay_factor=5)
            Update_Results_Dict['Boot_CMD2'] = net_connect.send_config_set(['config t','asdm image disk0:/{0}'.format(row['Target_FWX_FN']),'exit'],delay_factor=5)
        if 'ASA' in Device_Model:
            if row['HA'] != True:
                print(Paint_SVAR('[ {0} - IOS Update] Writing Memory.'.format(row['LocalIP']),'fg_blue','bg_white'))
                Update_Results_Dict['Show_Boot'] = net_connect.send_command_expect('show boot',delay_factor=5)
                Update_Results_Dict['Write_Mem'] = net_connect.send_command_expect('write mem',delay_factor=5)
                
                print(Paint_SVAR('[ {0} - IOS Update] Reloading device.'.format(row['LocalIP']),'fg_blue','bg_white'))
                Update_Results_Dict['reload'] = net_connect.send_command_timing('reload')
                Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')                    
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')                    
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')                    
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')                                  
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')                    
                    
                if Wait_for_Reboot(row) == True:                    
                    net_connect = Connect_Device(row,username,password)
                    count = 0 
                    while net_connect == False:
                        count += 1              
                        print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                        time.sleep(30)
                        net_connect = Connect_Device(row,username,password)
                        if count == 5:
                            print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                            return False
                return True
            else:
                print(Paint_SVAR('[ {0} - IOS Update] Writing Memory.'.format(row['LocalIP']),'fg_blue','bg_white'))
                Update_Results_Dict['Show_Boot'] = net_connect.send_command_expect('show boot',delay_factor=5)
                Update_Results_Dict['Write_Mem'] = net_connect.send_command_expect('write mem',delay_factor=5)
                if 'Security context mode: multiple' in context:
                    print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
                    net_connect.send_command_expect('changeto system')
                print(Paint_SVAR('[ {0} - IOS Update] Rebooting Standby.'.format(row['LocalIP']),'fg_blue','bg_white'))
                net_connect2 = Connect_Device(row2,username,password)
                count = 0 
                while net_connect2 == False:
                    count += 1              
                    print(Paint_SVAR('[ {0} - Reboot] Device connect failed after standby reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                    time.sleep(30)
                    net_connect2 = Connect_Device(row2,username,password)
                    if count == 5:
                        print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                        return False
                Update_Results_Dict['reload'] = net_connect2.send_command_timing('reload')
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect2.send_command_timing('Y')
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect2.send_command_timing('Y')
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect2.send_command_timing('Y')
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect2.send_command_timing('Y')
                if '?' in Update_Results_Dict['reload']:
                    Update_Results_Dict['reload'] = net_connect2.send_command_timing('Y')                    
                
                if Wait_For_Standby(row,net_connect,10,10) == True:
                    print(Paint_SVAR('[ {0} - IOS Update] Swaping Active Firewall and rebooting current.'.format(row['LocalIP']),'fg_blue','bg_white'))
                    net_connect = Connect_Device(row,username,password)
                    count = 0 
                    while net_connect == False:
                        count += 1              
                        print(Paint_SVAR('[ {0} - Reboot] Device connect failed after standby reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                        time.sleep(30)
                        net_connect = Connect_Device(row,username,password)
                        if count == 5:
                            print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                            return False
                    context = net_connect.send_command_expect('show mode')                            
                    if 'Security context mode: multiple' in context:
                        print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering Admin Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
                        net_connect.send_command_expect('changeto admin')
                    print(Paint_SVAR('[ {0} - Failover] Disabling failover.'.format(row['LocalIP']),'fg_blue','bg_white'))
                    Update_Results_Dict['NoFail'] = net_connect.send_command_timing('no failover active',delay_factor=5)
                    try:
                        if 'Security context mode: multiple' in context:
                            print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering System Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
                            net_connect.send_command_expect('changeto system')
                        Update_Results_Dict['reload'] = net_connect.send_command_timing('reload')
                        if '?' in Update_Results_Dict['reload']:
                            Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')
                        if '?' in Update_Results_Dict['reload']:
                            Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')
                        if '?' in Update_Results_Dict['reload']:
                            Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')
                        if '?' in Update_Results_Dict['reload']:
                            Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')
                    except:
                        print(Paint_SVAR('Reboot command issued irregular response, check device.','fg_red','bg_white'))
                        pass
                if Wait_for_Reboot(row) == True:                    
                    net_connect = Connect_Device(row,username,password)
                    count = 0 
                    while net_connect == False:
                        count += 1              
                        print(Paint_SVAR('[ {0} - Reboot] Device connect failed after reboot. Retry in 30'.format(row['LocalIP']),'fg_yellow','bg_white'))
                        time.sleep(30)
                        net_connect = Connect_Device(row,username,password)
                        if count == 5:
                            print(Paint_SVAR('[ {0} - Reboot] Device did not connect after FW Update. Verify Device.'.format(row['LocalIP'],'fg_red','bg_white')))
                            return False
                    context = net_connect.send_command_expect('show mode')                            
                    if 'Security context mode: multiple' in context:
                        print(Paint_SVAR('[ {0} - Multi-Context] MC Mode Multiple detected. Entering Admin Context.'.format(row['LocalIP']),'fg_blue','bg_white'))
                        net_connect.send_command_expect('changeto admin')
                    print(Paint_SVAR('[ {0} - Failover] Reactivating failover.'.format(row['LocalIP']),'fg_blue','bg_white'))
                    Update_Results_Dict['active'] = net_connect.send_command_timing('failover active')
                    
                    return True
        else:
            print(Paint_SVAR('[ {0} - IOS Update] Writing Memory.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['Show_Boot'] = net_connect.send_command_expect('show boot',delay_factor=5)
            Update_Results_Dict['Write_Mem'] = net_connect.send_command_expect('write mem',delay_factor=5)
        
            print(Paint_SVAR('[ {0} - IOS Update] Reloading device.'.format(row['LocalIP']),'fg_blue','bg_white'))
            Update_Results_Dict['reload'] = net_connect.send_command_timing('reload')
            Update_Results_Dict['reload'] = net_connect.send_command_timing('Y')
            return True

    # except Exception as err:
    #     msg = '[{0}] Error Completing update commands. : {1}'.format('IOS UPDATE', err)
    #     print(msg)
    #     errorLog.write(msg)

#	###############################################################################################
#	##################### HealthCheck functions ###################################################
#	###############################################################################################

        
def HealthChecks_Function(net_connect,row,Device_Model,prepost):

    
    print(Paint_SVAR('[ {1} - HealthChecks] Running {0} healthchecks...'.format(prepost,row['LocalIP']),'fg_blue','bg_white'))
    HealthCheck_dict = {}
    HealthCheck_dict['Settings'] = {}
    HealthCheck_dict['Settings']['Target_FW_FN'] = row['Target_FW_FN']
    
    
    print(Paint_SVAR('[ {0} - HealthChecks] Identifying Stack Switches if any...'.format(row['LocalIP']),'fg_blue','bg_white'))
    stack_count,SMaster = Gen_Stack_List(row,net_connect.send_command_expect('show switch', delay_factor=5))
       
    print(Paint_SVAR('[ {0} - HealthChecks] Collecting Device Show CMD Output...'.format(row['LocalIP']),'fg_blue','bg_white'))
    # try:
    if '3650' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '3650'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show switch', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show boot', delay_factor=5)
        HealthCheck_dict['Show_VLAN'] = net_connect.send_command_expect('show vlan', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_SW_Stack'] = net_connect.send_command_expect('show switch stack-ports', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show env all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = {}
        for x in stack_count:
            HealthCheck_dict['Show_License']['{0}'.format(x)] = net_connect.send_command_expect('show license all switch {0}'.format(x), delay_factor=5)

    elif '3750'  in Device_Model:
        HealthCheck_dict['Dev_Type'] = '3750'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show switch', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show boot', delay_factor=5)
        HealthCheck_dict['Show_VLAN'] = net_connect.send_command_expect('show vlan', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_SW_Stack'] = net_connect.send_command_expect('show switch stack-ports', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show env all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = {}
        for x in stack_count:
            HealthCheck_dict['Show_License']['{0}'.format(x)] = net_connect.send_command_expect('show license all switch {0}'.format(x), delay_factor=5)

    elif '3850' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '3850'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show  switch', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show  boot system', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show  cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show  ip eigrp neighb', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show  ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show  ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show  mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show  etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show  interface status', delay_factor=5)
        HealthCheck_dict['Show_SW_Stack'] = net_connect.send_command_expect('show  switch stack-ports', delay_factor=5)
        HealthCheck_dict['Show_Power'] = net_connect.send_command_expect('show  power', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show  spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show  inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show  environment all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show  run', delay_factor=15)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show  log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show  flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show  license right-to-use', delay_factor=5)
        HealthCheck_dict['RSA'] = net_connect.send_config_set(['crypto key gen rsa mod 1024','exit'], delay_factor=5)    

    elif '4500-noVSS' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '4500-noVSS'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show switch virtual', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5)

    elif '4500' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '4500'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show switch virtual', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5)        

    elif '4500-x VSS' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '4500-x VSS'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Switch'] = net_connect.send_command_expect('show switch virtual', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_VLP'] = net_connect.send_command_expect('show switch virtual link port', delay_factor=5)
        HealthCheck_dict['Show_VLPC'] = net_connect.send_command_expect('show switch virtual link port-channel', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory all', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5) 
    
    elif '4506' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '4506'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Bootflash'] = net_connect.send_command_expect('show bootflash:', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory all', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5) 

    elif 'C4510R' in Device_Model:
        HealthCheck_dict['Dev_Type'] = 'C4510R'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Bootflash'] = net_connect.send_command_expect('show bootflash:', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)        
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory all', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5)         

    elif 'IE' in Device_Model:
        HealthCheck_dict['Dev_Type'] = 'IE'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show boot', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory all', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show env all', delay_factor=5)
        HealthCheck_dict['Show_Power'] = net_connect.send_command_expect('show power inline', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Flash'] = net_connect.send_command_expect('show flash', delay_factor=5)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license summary', delay_factor=5)            

    elif '9300' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '9300'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Platform'] = net_connect.send_command_expect('show platform', delay_factor=5)
        HealthCheck_dict['Show_module'] = net_connect.send_command_expect('show module', delay_factor=5)
        HealthCheck_dict['Show_redundancy'] = net_connect.send_command_expect('show redundancy', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show boot', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License'] = net_connect.send_command_expect('show license all', delay_factor=5)

    elif '9400' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '9400'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Platform'] = net_connect.send_command_expect('show platform', delay_factor=5)
        HealthCheck_dict['Show_module'] = net_connect.send_command_expect('show module', delay_factor=5)
        HealthCheck_dict['Show_redundancy'] = net_connect.send_command_expect('show redundancy', delay_factor=5)
        HealthCheck_dict['Show_SW_IOMD_REDN'] = net_connect.send_command_expect('show platform software iomd redun', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License_rtu'] = net_connect.send_command_expect('show license right-to-use', delay_factor=5)
        HealthCheck_dict['Show_License_fv'] = net_connect.send_command_expect('show license feature-version', delay_factor=5)
        HealthCheck_dict['remove_inactive'] = net_connect.send_command_expect('install remove inactive', delay_factor=5)
        HealthCheck_dict['Show_Dir_Flash'] = net_connect.send_command_expect('dir flash:', delay_factor=5)

    elif '9500' in Device_Model:
        HealthCheck_dict['Dev_Type'] = '9500'
        HealthCheck_dict['Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['Show_Platform'] = net_connect.send_command_expect('show platform', delay_factor=5)
        HealthCheck_dict['Show_module'] = net_connect.send_command_expect('show module', delay_factor=5)
        HealthCheck_dict['Show_redundancy'] = net_connect.send_command_expect('show redundancy', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show bootvar', delay_factor=5)
        HealthCheck_dict['Show_CDP'] = net_connect.send_command_expect('show cdp neighbors', delay_factor=5)
        HealthCheck_dict['Show_STP'] = net_connect.send_command_expect('show spanning-tree', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_ARP'] = net_connect.send_command_expect('show ip arp', delay_factor=5)
        HealthCheck_dict['Show_MAC'] = net_connect.send_command_expect('show mac address-table', delay_factor=5)
        HealthCheck_dict['Show_EtherChannel'] = net_connect.send_command_expect('show etherchannel summary', delay_factor=5)
        HealthCheck_dict['Show_Int_Status'] = net_connect.send_command_expect('show interface status', delay_factor=5)
        HealthCheck_dict['Show_Inv'] = net_connect.send_command_expect('show inventory', delay_factor=5)
        HealthCheck_dict['Show_Env'] = net_connect.send_command_expect('show environment all', delay_factor=5)
        HealthCheck_dict['Show_Run'] = net_connect.send_command_expect('show run', delay_factor=5)
        HealthCheck_dict['Show_Log'] = net_connect.send_command_expect('show log', delay_factor=15)
        HealthCheck_dict['Show_Dir'] = net_connect.send_command_expect('dir all-filesystems', delay_factor=5)
        HealthCheck_dict['Show_License_rtu'] = net_connect.send_command_expect('show license right-to-use', delay_factor=5)
        HealthCheck_dict['Show_License_fv'] = net_connect.send_command_expect('show license feature-version', delay_factor=5)

    elif 'ASA' in Device_Model:
        HealthCheck_dict['ASA_Show_IP'] = net_connect.send_command_expect('show int ip br', delay_factor=5)
        HealthCheck_dict['ASA_Show_Ver'] = net_connect.send_command_expect('show ver', delay_factor=5)
        HealthCheck_dict['ASA_Show_Dir'] = net_connect.send_command_expect('dir', delay_factor=5)
        HealthCheck_dict['ASA_Show_Failover'] = net_connect.send_command_expect('show failover state', delay_factor=5)
        HealthCheck_dict['ASA_Show_DHCP'] = net_connect.send_command_expect('show dhcpd bind', delay_factor=5)
        HealthCheck_dict['ASA_Show_WebVPN'] = net_connect.send_command_expect('show webvpn anyconnect', delay_factor=5)
        HealthCheck_dict['Show_Route'] = net_connect.send_command_expect('show ip route', delay_factor=5)
        HealthCheck_dict['Show_EIGRP'] = net_connect.send_command_expect('show ip eigrp neighbors', delay_factor=5)
        HealthCheck_dict['ASA_Show_OSPF'] = net_connect.send_command_expect('show ip ospf neighbors', delay_factor=5)
        HealthCheck_dict['Show_Boot'] = net_connect.send_command_expect('show boot', delay_factor=5)

    Combined_Return = { 'Raw_Data':HealthCheck_dict,'Extracted_Data': Parse_HealthChecks(row,HealthCheck_dict) }
    # except Exception as err:
    #     msg = '[{0}] Error Completing HealthCheck commands. : {1}'.format('HealthCheck', err)
    #     print(msg)
    #     errorLog.write(msg)            
    return Combined_Return

def Parse_HealthChecks(row,HealthCheck_dict):
    print(Paint_SVAR('Parsing healthchecks...','fg_blue','bg_white'))
    Extracted_Data = {}
    # try:
    if 'Show_Switch' in HealthCheck_dict.keys():
        Extracted_Data['Show_Switch'] = Parse_Show_Switch(row,HealthCheck_dict['Show_Switch'])
    if 'Show_Ver' in HealthCheck_dict.keys():
        try:
            Extracted_Data['Show_Ver'] =  re.sub(r'flash:/|flash://|\"','',str(["".join(x) for x in re.findall(r'Active-image : (.*)$|System image file is (.*)$',HealthCheck_dict['Show_Ver'],re.MULTILINE)][0])) 
            Extracted_Data['Current_Ver'] =  re.sub(',','',re.findall(r'\d*\.\d*\(\S*\)\S*',HealthCheck_dict['Show_Ver'],re.MULTILINE)[0])
        except:
            Extracted_Data['Show_Ver'] =  re.sub(r'flash:/|flash://|\"','',str(["".join(x) for x in re.findall(r'Active-image : (.*)$|System image file is (.*)$',HealthCheck_dict['Show_Ver'],re.MULTILINE)][0])) 
            Extracted_Data['Current_Ver'] =  re.sub(',','',re.findall(r'\d*\.\d*\.\d*',HealthCheck_dict['Show_Ver'],re.MULTILINE)[0])
    if 'Show_Platform' in HealthCheck_dict.keys():
        Extracted_Data['Show_Platform'] = Parse_Show_platform(row,HealthCheck_dict['Show_Platform'])
    if 'Show_module' in HealthCheck_dict.keys():
        Extracted_Data['Show_module'] = Parse_Show_Module(row,HealthCheck_dict['Show_module'])
    if 'Show_redundancy' in HealthCheck_dict.keys():
        Extracted_Data['Show_redundancy'] = Parse_Show_Redundandcy(row,HealthCheck_dict['Show_redundancy'])
    if 'Show_Boot' in HealthCheck_dict.keys():
        Extracted_Data['Show_Boot'] = Parse_Show_bootvar(row,HealthCheck_dict['Show_Boot'])
    if 'Show_CDP' in HealthCheck_dict.keys():
        Extracted_Data['Show_CDP'] = Parse_Show_CDP(row,HealthCheck_dict['Show_CDP'])
    if 'Show_STP' in HealthCheck_dict.keys():
        Extracted_Data['Show_STP'] = Parse_Show_Spanning_Tree(row,HealthCheck_dict['Show_STP'])
    if 'Show_Route' in HealthCheck_dict.keys():
        Extracted_Data['Show_Route'] = Parse_Show_Route_Summary(row,HealthCheck_dict['Show_Route'])
    if 'Show_ARP' in HealthCheck_dict.keys():
        Extracted_Data['Show_ARP'] = Parse_Show_ARP(row,HealthCheck_dict['Show_ARP'])
    if 'Show_MAC' in HealthCheck_dict.keys():
        Extracted_Data['Show_MAC'] = Parse_Show_MAC(row,HealthCheck_dict['Show_MAC'])
    if 'Show_EtherChannel' in HealthCheck_dict.keys():
        Extracted_Data['Show_EtherChannecdl'] = Parse_Show_EtherChannel(row,HealthCheck_dict['Show_EtherChannel'])
    if 'Show_Int_Status' in HealthCheck_dict.keys():
        Extracted_Data['Show_Int_Status'] = Parse_Show_Int_Status(row,HealthCheck_dict['Show_Int_Status'],HealthCheck_dict['Show_VLAN'])
    if 'Show_Inv' in HealthCheck_dict.keys():
        Extracted_Data['Show_Inv'] = Parse_Show_Inv(row,HealthCheck_dict['Show_Inv'])
    if 'Show_Env' in HealthCheck_dict.keys():
        Extracted_Data['Show_Env'] = Parse_Show_Env(row,HealthCheck_dict['Show_Env'])
    if 'Show_EIGRP' in HealthCheck_dict.keys():
        Extracted_Data['Show_EIGRP'] = Parse_Show_EIGRP_Neighbors(row,HealthCheck_dict['Show_EIGRP'])
    if 'Show_VLAN' in HealthCheck_dict.keys():
        Extracted_Data['Show_VLAN'] = Parse_Show_VLAN(row,HealthCheck_dict['Show_VLAN'])
    if 'Show_Run' in HealthCheck_dict.keys():
        Extracted_Data['Show_Run_INT'] = Parse_Show_Run_Int(row,HealthCheck_dict['Show_Run'])
    if 'Show_License' in HealthCheck_dict.keys():
        Extracted_Data['Show_License'] = Parse_Show_Lic(row,HealthCheck_dict['Show_License'])

    if 'ASA_Show_IP' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_IP'] = Parse_ASA_Show_IP(row,HealthCheck_dict['ASA_Show_IP'])
    if 'ASA_Show_Ver' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_Ver'] = Parse_ASA_Show_Ver(row,HealthCheck_dict['ASA_Show_Ver'])
    if 'ASA_Show_Dir' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_Dir'] = Parse_ASA_Show_Dir(row,HealthCheck_dict['ASA_Show_Dir'])
    if 'ASA_Show_Failover' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_Failover'] = Parse_ASA_Show_Failover(row,HealthCheck_dict['ASA_Show_Failover']) 
    if 'ASA_Show_DHCP' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_DHCP'] = Parse_ASA_Show_DHCP(row,HealthCheck_dict['ASA_Show_DHCP'])
    if 'ASA_Show_WebVPN' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_WebVPN'] = Parse_ASA_Show_WebVPN(row,HealthCheck_dict['ASA_Show_WebVPN'])       
    if 'ASA_Show_OSPF' in HealthCheck_dict.keys():
        Extracted_Data['ASA_Show_OSPF'] = Parse_ASA_Show_OSPF(row,HealthCheck_dict['ASA_Show_OSPF'])       

    # except Exception as err:
    #     msg = '[{0}] Error Parsing HealthCheck commands. : {1}'.format('Extract', err)
    #     print(msg)
    #     errorLog.write(msg)               
    return Extracted_Data

def ComparePrePost(PreCheck,PostCheck):
    Diff_Report = {}
    # try:
    
    if 'Show_Switch' in PreCheck['Extracted_Data'].keys() and 'Show_Switch' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_Switch'].keys()) != 0:
            if 'Show_Switch' not in Diff_Report.keys():
                Diff_Report['Show_Switch'] = {}
            for switch_num, data in PreCheck['Extracted_Data']['Show_Switch'].items():
                if switch_num in PostCheck['Extracted_Data']['Show_Switch'].keys():
                    if PreCheck['Extracted_Data']['Show_Switch'][switch_num]['Switch_state'] == PostCheck['Extracted_Data']['Show_Switch'][switch_num]['Switch_state']:
                        Diff_Report['Show_Switch'] = {'Status': 'Passed', 'Type' : 'Switch state'}
                        pass
                    else:
                        Diff_Report['Show_Switch'][switch_num] = {'Status': 'Failed', 'Type' : 'Stack Switch {0} Not Found.'.format(switch_num), 'Pre-Value': PreCheck['Extracted_Data']['Show_Switch'][switch_num]['Switch_state'], 'Post-Value': 'Not Present.'}
                else:
                    Diff_Report['Show_Switch'][switch_num] = {'Status': 'Failed', 'Type' : 'Switch state', 'Pre-Value': PreCheck['Extracted_Data']['Show_Switch'][switch_num]['Switch_state'], 'Post-Value': 'None'}
    if 'Show_Ver' in PreCheck['Extracted_Data'].keys() and 'Show_Ver' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_Ver']) != 0:
            if 'Show_Ver' not in Diff_Report.keys():
                Diff_Report['Show_Ver'] = {}
            oldfirmware = PreCheck['Extracted_Data']['Show_Ver']
            current_firmware = PostCheck['Extracted_Data']['Show_Ver']
            if oldfirmware != current_firmware:
                pass
            else:
                Diff_Report['Show_Ver'] = {'Status': 'Failed', 'Type' : 'Incorrect Firmware', 'Pre-Value': oldfirmware, 'Post-Value': current_firmware}
            if current_firmware != PreCheck['Raw_Data']['Settings']['Target_FW_FN']:
                Diff_Report['Show_Ver'] = {'Status': 'Failed', 'Type' : 'Incorrect Firmware', 'Pre-Value': PreCheck['Raw_Data']['Settings']['Target_FW_FN'], 'Post-Value': current_firmware}
            else:
                Diff_Report['Show_Ver'] = {'Status': 'Passed', 'Type' : 'Correct Firmware', 'Pre-Value': PreCheck['Raw_Data']['Settings']['Target_FW_FN'], 'Post-Value': current_firmware}
    if 'Show_Platform' in PreCheck['Extracted_Data'].keys() and 'Show_Platform' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_Platform'].keys()) != 0:
            if 'Show_Platform' not in Diff_Report.keys():
                Diff_Report['Show_Platform'] = {}
            for Slot, data in PreCheck['Extracted_Data']['Show_Platform'].items():
                if PreCheck['Extracted_Data']['Show_Platform'][Slot]['State'] == PostCheck['Extracted_Data']['Show_Platform'][Slot]['State']:
                    pass
                else:
                    Diff_Report['Show_Platform'][Slot] =  {'Status': 'Failed', 'Type' : 'Platform state', 'Pre-Value': PreCheck['Extracted_Data']['Show_Platform'][Slot]['State'], 'Post-Value': PostCheck['Extracted_Data']['Show_Platform'][Slot]['State']}
            if len(Diff_Report['Show_Platform'].keys()) == 0:
                Diff_Report['Show_Platform'] =  {'Status': 'Passed', 'Type' : 'Platform state'}
    if 'Show_module' in PreCheck['Extracted_Data'].keys() and 'Show_module' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_module'].keys()) != 0:
            if 'Show_module' not in Diff_Report.keys():
                Diff_Report['Show_module'] = {}
            for slot, data in PreCheck['Extracted_Data']['Show_module'].items():
                if PreCheck['Extracted_Data']['Show_module'][slot]['Mod_status'] == PostCheck['Extracted_Data']['Show_module'][slot]['Mod_status']:
                    pass
                else:
                    Diff_Report['Show_module'][slot] = {'Status': 'Failed', 'Type' : 'Module state', 'Pre-Value': PreCheck['Extracted_Data']['Show_module'][slot]['Mod_status'], 'Post-Value': PostCheck['Extracted_Data']['Show_module'][slot]['Mod_status']}
            if len(Diff_Report['Show_module'].keys()) == 0:
                Diff_Report['Show_module'] = {'Status': 'Passed', 'Type' : 'Module state'}
    if 'Show_redundancy' in PreCheck['Extracted_Data'].keys() and 'Show_redundancy' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_redundancy'].keys()) != 0:
            if 'Show_redundancy' not in Diff_Report.keys():
                Diff_Report['Show_redundancy'] = {}
            if PreCheck['Extracted_Data']['Show_redundancy']['CurrentState'] == PostCheck['Extracted_Data']['Show_redundancy']['CurrentState']:
                Diff_Report['Show_redundancy'] = {'Status': 'Passed', 'Type' : 'Redundancy_state'}
                pass
            else:
                Diff_Report['Show_redundancy'] = {'Status': 'Failed', 'Type' : 'Redundancy_state', 'Pre-Value': PreCheck['Extracted_Data']['Show_redundancy']['CurrentState'], 'Post-Value': PostCheck['Extracted_Data']['Show_redundancy']['CurrentState']}

    # if 'Show_Boot' in PreCheck['Extracted_Data'].keys() and 'Show_Boot' in PostCheck['Extracted_Data'].keys():
    #     if 'Show_Boot' not in Diff_Report.keys():
    #         Diff_Report['Show_Boot'] = {}

    if 'Show_CDP' in PreCheck['Extracted_Data'].keys() and 'Show_CDP' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_CDP'].keys()) != 0:
            if 'Show_CDP' not in Diff_Report.keys():
                Diff_Report['Show_CDP'] = {}
            
            for Interface,Data in PreCheck['Extracted_Data']['Show_CDP'].items():
                if Interface in PostCheck['Extracted_Data']['Show_CDP'].keys():
                    pass              
                else:
                    Diff_Report['Show_CDP'][Interface] = {'Status': 'Failed', 'Type' : 'Int not present after change.', 'Pre-Value': Interface, 'Post-Value': 'Empty' }
            if len(Diff_Report['Show_CDP'].keys()) == 0:
                Diff_Report['Show_CDP'] = {'Status': 'Passed', 'Type' : 'CDP state'}
    if 'Show_STP' in PreCheck['Extracted_Data'].keys() and 'Show_STP' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_STP'].keys()) != 0:
            if 'Show_STP' not in Diff_Report.keys():
                Diff_Report['Show_STP'] = {}
            for VLAN, data in PreCheck['Extracted_Data']['Show_STP'].items():
                if VLAN not in Diff_Report['Show_STP'].keys():
                    Diff_Report['Show_STP'][VLAN] = {} 
                if 'Root_Pri' in PreCheck['Extracted_Data']['Show_STP'][VLAN]:
                    if PreCheck['Extracted_Data']['Show_STP'][VLAN]['Root_Pri'] != PostCheck['Extracted_Data']['Show_STP'][VLAN]['Root_Pri'] :
                        Diff_Report['Show_STP'][VLAN]['Root_Pri'] = {'Status': 'Failed', 'Type' : 'Root Pri mismatch post change for vlan {0}'.format(VLAN), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN]['Root_Pri'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN]['Root_Pri'] }
                if PreCheck['Extracted_Data']['Show_STP'][VLAN]['Hello'] != PostCheck['Extracted_Data']['Show_STP'][VLAN]['Hello'] :
                    Diff_Report['Show_STP'][VLAN]['Hello'] = {'Status': 'Failed', 'Type' : 'Hello timer mismatch post change for vlan {0}'.format(VLAN), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN]['Hello'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN]['Hello'] }
                if PreCheck['Extracted_Data']['Show_STP'][VLAN]['Max_Age'] != PostCheck['Extracted_Data']['Show_STP'][VLAN]['Max_Age'] :
                    Diff_Report['Show_STP'][VLAN]['Max_Age'] = {'Status': 'Failed', 'Type' : 'Max_Age mismatch post change for vlan {0}'.format(VLAN), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN]['Max_Age'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN]['Max_Age'] }
                if PreCheck['Extracted_Data']['Show_STP'][VLAN]['Forward_Delay'] != PostCheck['Extracted_Data']['Show_STP'][VLAN]['Forward_Delay'] :
                    Diff_Report['Show_STP'][VLAN]['Forward_Delay']= {'Status': 'Failed', 'Type' : 'Forward_Delay mismatch post change for vlan {0}'.format(VLAN), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN]['Forward_Delay'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN]['Forward_Delay'] }
                for Interface, data in PreCheck['Extracted_Data']['Show_STP'][VLAN].items():
                    if Interface in ['Root_Pri','Hello','Max_Age','Forward_Delay']:
                        continue
                    elif Interface not in Diff_Report['Show_STP'][VLAN].keys():
                        Diff_Report['Show_STP'][VLAN]['Interface'] = {} 
                    if Interface not in PostCheck['Extracted_Data']['Show_STP'][VLAN].keys():
                        Diff_Report['Show_STP'][VLAN][Interface] = {'Status': 'Failed', 'Type' : 'Interface {0} missing from stp post change.'.format(Interface), 'Pre-Value': Interface, 'Post-Value': 'Empty' }
                    else:
                        if PreCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['Role'] != PostCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['Role']:
                            Diff_Report['Show_STP'][VLAN][Interface]['Role'] = {'Status': 'Failed', 'Type' : 'Interface {0} Role different post change.'.format(Interface), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['Role'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['Role']}
                        if PreCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['FWD_State'] != PostCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['FWD_State']:
                            Diff_Report['Show_STP'][VLAN][Interface]['FWD_State'] = {'Status': 'Failed', 'Type' : 'FWD State different post change.'.format(Interface), 'Pre-Value': PreCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['FWD_State'], 'Post-Value': PostCheck['Extracted_Data']['Show_STP'][VLAN][Interface]['FWD_State']}
            for key in Diff_Report['Show_STP'].keys():
                if len(Diff_Report['Show_STP'][key].keys()) == 0:
                    clear = True
                    continue
                else: 
                    clear = False
                    break
            if clear == True:
                Diff_Report['Show_STP'] = {}
                Diff_Report['Show_STP'] = {'Status': 'Passed', 'Type' : 'STP state'}

    if 'Show_Route' in PreCheck['Extracted_Data'].keys() and 'Show_Route' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_Route'].keys()) != 0:
            if 'Show_Route' not in Diff_Report.keys():
                Diff_Report['Show_Route'] = {}
            if int(PreCheck['Extracted_Data']['Show_Route']['Total']) == int(PostCheck['Extracted_Data']['Show_Route']['Total']):
                Diff_Report['Show_Route'] = {'Status': 'Passed', 'Type' : 'Route Count'}
                pass
            else:
                for cidr, data in PreCheck['Extracted_Data']['Show_Route'].items():
                    if int(PreCheck['Extracted_Data']['Show_Route'][cidr]) == int(PostCheck['Extracted_Data']['Show_Route'][cidr]):
                        pass
                    else:
                        Diff_Report['Show_Route'][cidr] = {'Status': 'Failed', 'Type' : 'Route Count Mismatch. Cidr Length : {0}'.format(cidr), 'Pre-Value': PreCheck['Extracted_Data']['Show_Route'][cidr], 'Post-Value': PostCheck['Extracted_Data']['Show_Route'][cidr] }
                if len(Diff_Report['Show_Route'].keys()) == 0:
                    Diff_Report['Show_Route'] = {'Status': 'Passed', 'Type' : 'Route Count'}
    if 'Show_ARP' in PreCheck['Extracted_Data'].keys() and 'Show_ARP' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_ARP'].keys()) != 0:
            if 'Show_ARP' not in Diff_Report.keys():
                Diff_Report['Show_ARP'] = {}
            for ipaddress, data in PreCheck['Extracted_Data']['Show_ARP'].items():
                if ipaddress in PostCheck['Extracted_Data']['Show_ARP'].keys():
                    if PreCheck['Extracted_Data']['Show_ARP'][ipaddress]['MAC'] == PostCheck['Extracted_Data']['Show_ARP'][ipaddress]['MAC']:
                        pass
                    else:
                        Diff_Report['Show_ARP'][ipaddress] = {'Status': 'Failed', 'Type' : 'Arp reports different MAC for IP {0} after change.'.format(ipaddress), 'Pre-Value': PreCheck['Extracted_Data']['Show_ARP'][ipaddress]['MAC'], 'Post-Value': PostCheck['Extracted_Data']['Show_ARP'][ipaddress]['MAC'] }
                else:
                    Diff_Report['Show_ARP'][ipaddress] = {'Status': 'Failed', 'Type' : 'Arp not present for IP {0} after change.'.format(ipaddress), 'Pre-Value': ipaddress, 'Post-Value': 'Empty'}
            if len(Diff_Report['Show_ARP'].keys()) == 0:
                Diff_Report['Show_Route'] = {'Status': 'Passed', 'Type' : 'ARP Count'}

    if 'Show_MAC' in PreCheck['Extracted_Data'].keys() and 'Show_MAC' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_MAC'].keys()) != 0:
            if 'Show_MAC' not in Diff_Report.keys():
                Diff_Report['Show_MAC'] = {}
                for MAC, Data in PreCheck['Extracted_Data']['Show_MAC']['static'].items():
                    if MAC not in PostCheck['Extracted_Data']['Show_MAC']['static'].keys():
                        Diff_Report['Show_MAC'][MAC] = {'Status': 'Failed', 'Type' : 'Static MAC {0} not present after change.'.format(MAC), 'Pre-Value': MAC, 'Post-Value': 'Empty'}

                for MAC, Data in PreCheck['Extracted_Data']['Show_MAC']['dynamic'].items():
                    if MAC not in PostCheck['Extracted_Data']['Show_MAC']['dynamic'].keys():
                        Diff_Report['Show_MAC'][MAC] = {'Status': 'Failed', 'Type' : 'Dynamic MAC {0} not present after change.'.format(MAC), 'Pre-Value': MAC, 'Post-Value': 'Empty'}
            if len(Diff_Report['Show_MAC'].keys()) == 0:
                Diff_Report['Show_MAC'] = {'Status': 'Passed', 'Type' : 'MAC Count'}

    if 'Show_EtherChannel' in PreCheck['Extracted_Data'].keys() and 'Show_EtherChannel' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_EtherChannel'].keys()) != 0:
            if 'Show_EtherChannel' not in Diff_Report.keys():
                Diff_Report['Show_EtherChannel'] = {}
                for AggPort, data in PreCheck['Extracted_Data']['Show_EtherChannel'].items():
                    if AggPort not in PostCheck['Extracted_Data']['Show_EtherChannel'].keys():
                        Diff_Report['Show_EtherChannel'][AggPort] = {'Status': 'Failed', 'Type' : 'AggPort {0} not present after change.'.format(AggPort), 'Pre-Value': AggPort, 'Post-Value': 'Empty'}
                        continue
                    else:
                        for Port in PreCheck['Extracted_Data']['Show_EtherChannel'][AggPort]['Ports']:
                            if Port not in PostCheck['Extracted_Data']['Show_EtherChannel'][AggPort]['Ports']:
                                if 'AggPort' not in Diff_Report['Show_EtherChannel'].keys():
                                    Diff_Report['Show_EtherChannel']['AggPort'] = {}
                                Diff_Report['Show_EtherChannel'][AggPort]['port'] = {'Status': 'Failed', 'Type' : 'Port: {0} not present in Agg: {1} after change.'.format(Port,AggPort), 'Pre-Value': Port, 'Post-Value': 'Empty'}
                if len(Diff_Report['Show_EtherChannel'].keys()) == 0:
                    Diff_Report['Show_EtherChannel'] = {'Status': 'Passed', 'Type' : 'EtherChannel State'}

    if 'Show_Int_Status' in PreCheck['Extracted_Data'].keys() and 'Show_Int_Status' in PostCheck['Extracted_Data'].keys():
        if len(PreCheck['Extracted_Data']['Show_Int_Status'].keys()) != 0:
            if 'Show_Int_Status' not in Diff_Report.keys():
                Diff_Report['Show_Int_Status'] = {}
            for Interface, data in PreCheck['Extracted_Data']['Show_Int_Status'].items():
                if Interface not in PostCheck['Extracted_Data']['Show_Int_Status'].keys():
                    Diff_Report['Show_Int_Status'][Interface] = {'Status': 'Failed', 'Type' : 'Interface {0} not present after change.'.format(Interface), 'Pre-Value': Interface, 'Post-Value': 'Empty', 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
                else:          
                    if PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['State'] != PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['State']:
                        if Interface not in Diff_Report['Show_Int_Status'].keys():
                            Diff_Report['Show_Int_Status'][Interface] = {} 
                        Diff_Report['Show_Int_Status'][Interface]['State'] = {'Status': 'Failed', 'Type' : 'Interface {0} state changed after change.'.format(Interface), 'Pre-Value':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['State'], 'Post-Value': PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['State'], 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
                    if PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Vlan'] != PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Vlan']:
                        if Interface not in Diff_Report['Show_Int_Status'].keys():
                            Diff_Report['Show_Int_Status'][Interface] = {} 
                        Diff_Report['Show_Int_Status'][Interface]['Vlan'] = {'Status': 'Failed', 'Type' : 'Interface {0} Vlan changed after change.'.format(Interface), 'Pre-Value':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Vlan'], 'Post-Value': PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Vlan'], 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
                    if PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Duplex'] != PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Duplex']:
                        if Interface not in Diff_Report['Show_Int_Status'].keys():
                            Diff_Report['Show_Int_Status'][Interface] = {} 
                        Diff_Report['Show_Int_Status'][Interface]['Duplex'] = {'Status': 'Failed', 'Type' : 'Interface {0} duplex changed after change.'.format(Interface), 'Pre-Value':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Duplex'], 'Post-Value': PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Duplex'], 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
                    if PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Speed'] != PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Speed']:
                        Diff_Report['Show_Int_Status'][Interface]['Speed'] = {'Status': 'Failed', 'Type' : 'Interface {0} Speed changed after change.'.format(Interface), 'Pre-Value':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Speed'], 'Post-Value': PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Speed'], 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
                        if Interface not in Diff_Report['Show_Int_Status'].keys():
                            Diff_Report['Show_Int_Status'][Interface] = {} 
                    if PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Type'] != PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Type']:
                        if Interface not in Diff_Report['Show_Int_Status'].keys():
                            Diff_Report['Show_Int_Status'][Interface] = {} 
                        Diff_Report['Show_Int_Status'][Interface]['Type'] = {'Status': 'Failed', 'Type' : 'Interface {0} Type changed after change.'.format(Interface), 'Pre-Value':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Type'], 'Post-Value': PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['Type'], 'Config' : PostCheck['Extracted_Data']['Show_Run_INT'][Interface],'Pre-RAW':  PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Post-RAW':  PostCheck['Extracted_Data']['Show_Int_Status'][Interface]['RAW'], 'Header': PreCheck['Extracted_Data']['Show_Int_Status'][Interface]['Header']}
        if len(Diff_Report['Show_Int_Status'].keys()) == 0:
            Diff_Report['Show_Int_Status'] = {'Status': 'Passed', 'Type' : 'Interface State'}
        print(Diff_Report['Show_Int_Status'])

    if 'Show_Inv' in PreCheck['Extracted_Data'].keys() and 'Show_Inv' in PostCheck['Extracted_Data'].keys():
        if 'Show_Inv' not in Diff_Report.keys():
            Diff_Report['Show_Inv'] = {}
        for Module, data in PreCheck['Extracted_Data']['Show_Inv'].items():
            if Module not in PostCheck['Extracted_Data']['Show_Inv'].keys():
                Diff_Report['Show_Inv'][Mod] = {'Status': 'Failed', 'Type' : 'Module {0} not present after change.'.format(Mod), 'Pre-Value':  Mod, 'Post-Value': 'Empty'}
        if len(Diff_Report['Show_Inv'].keys()) == 0:
            Diff_Report['Show_Inv'] = {'Status': 'Passed', 'Type' : 'Inventory State'}

    if 'Show_License' in PreCheck['Extracted_Data'].keys() and 'Show_License' in PostCheck['Extracted_Data'].keys():
        if 'Show_License' not in Diff_Report.keys():
            Diff_Report['Show_Env'] = {}
        for switch, data in PreCheck['Extracted_Data']['Show_License'].items():
            if len(data.keys()) > 0:
                if len(data['Feature']) == len(PostCheck['Extracted_Data']['Show_License'][switch]['Feature']):
                    Diff_Report['Show_License'][switch] = {'Status': 'Passed', 'Type' : 'All license present after update.', 'Pre-Value': PreCheck['Extracted_Data']['Show_License'][switch]['Feature'] , 'Post-Value':  PostCheck['Extracted_Data']['Show_License'][switch]['Feature']}
                else:
                    Diff_Report['Show_License'][switch] = {'Status': 'Failed', 'Type' : 'Some license not present after update.', 'Pre-Value': PreCheck['Extracted_Data']['Show_License'][switch]['Feature'] , 'Post-Value':  PostCheck['Extracted_Data']['Show_License'][switch]['Feature']}

    # if 'Show_Env' in PreCheck['Extracted_Data'].keys() and 'Show_Env' in PostCheck['Extracted_Data'].keys():
    #     if 'Show_Env' not in Diff_Report.keys():
    #         Diff_Report['Show_Env'] = {}

    if 'Show_EIGRP' in PreCheck['Extracted_Data'].keys() and 'Show_EIGRP' in PostCheck['Extracted_Data'].keys():
        if 'Show_EIGRP' not in Diff_Report.keys():
            Diff_Report['Show_EIGRP'] = {}
        for Neighbor, data in PreCheck['Extracted_Data']['Show_EIGRP'].items():
            if Neighbor not in PostCheck['Extracted_Data']['Show_EIGRP'].keys():
                Diff_Report['Show_EIGRP'][Neighbor] = {'Status': 'Failed', 'Type' : 'EIGRP Neighbor {0} not present after change.'.format(Neighbor), 'Pre-Value':  Neighbor, 'Post-Value': 'Empty'}
        if len(Diff_Report['Show_EIGRP'].keys()) == 0:
            Diff_Report['Show_EIGRP'] = {'Status': 'Passed', 'Type' : 'EIGRP State'} 


    if 'ASA_Show_IP' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_IP' in PostCheck['Extracted_Data'].keys():
        if 'ASA_Show_IP' not in Diff_Report.keys():
            Diff_Report['ASA_Show_IP'] = {}        
        for interface, details in PreCheck['Extracted_Data']['ASA_Show_IP'].items():
            if interface in PostCheck['Extracted_Data']['ASA_Show_IP'].keys():
                if interface not in Diff_Report.keys():
                    Diff_Report['ASA_Show_IP'][interface] = {}                        
                if PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin'] == PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin']:
                    Diff_Report['ASA_Show_IP'][interface]['Admin'] = {'Status': 'Passed', 'Type' : '{0} Interface Admin state equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin']}
                else:
                    Diff_Report['ASA_Show_IP'][interface]['Admin'] = {'Status': 'Failed', 'Type' : '{0} Interface Admin state not equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Admin']}

                if PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper'] == PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper']:
                    Diff_Report['ASA_Show_IP'][interface]['Oper'] = {'Status': 'Passed', 'Type' : '{0} Interface Oper state equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper']}
                else:
                    Diff_Report['ASA_Show_IP'][interface]['Oper'] = {'Status': 'Failed', 'Type' : '{0} Interface Oper state not equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['Oper']}

                if PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips'] == PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips']:
                    Diff_Report['ASA_Show_IP'][interface]['ips'] = {'Status': 'Passed', 'Type' : '{0} Interface IPs equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips']}
                else:
                    Diff_Report['ASA_Show_IP'][interface]['ips'] = {'Status': 'Failed', 'Type' : '{0} Interface IPs not equal to pre-check.'.format(interface), 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_IP'][interface]['ips']}

    if 'ASA_Show_Ver' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_Ver' in PostCheck['Extracted_Data'].keys():
        if 'ASA_Show_Ver' not in Diff_Report.keys():
            Diff_Report['ASA_Show_Ver'] = {}        
        if PreCheck['Extracted_Data']['ASA_Show_Ver'] == PostCheck['Extracted_Data']['ASA_Show_Ver']:
            Diff_Report['ASA_Show_Ver'] = {'Status': 'Passed', 'Type' : 'ASA_Show_ver state did not change.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Ver'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Ver']}
        else:
            Diff_Report['ASA_Show_Ver'] = {'Status': 'Failed', 'Type' : 'ASA_Show_ver state changed.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Ver'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Ver']}
        
    
    # if 'ASA_Show_Dir' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_Dir' in PostCheck['Extracted_Data'].keys():
    #     pass

    if 'ASA_Show_Failover' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_Failover' in PostCheck['Extracted_Data'].keys():
        if 'ASA_Show_Failover' not in Diff_Report.keys():
            Diff_Report['ASA_Show_Failover'] = {}        
        if PreCheck['Extracted_Data']['ASA_Show_Failover']['MyState'] == PostCheck['Extracted_Data']['ASA_Show_Failover']['MyState']:
            Diff_Report['ASA_Show_Failover'] = {'Status': 'Passed', 'Type' : 'ASA_Show_Failover state did not change.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Failover']['MyState'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Failover']['MyState']}
        else:
            Diff_Report['ASA_Show_Failover'] = {'Status': 'Failed', 'Type' : 'ASA_Show_Failover state changed.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Failover']['MyState'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Failover']['MyState']}
        if PreCheck['Extracted_Data']['ASA_Show_Failover']['MyRank'] == PostCheck['Extracted_Data']['ASA_Show_Failover']['MyRank']:
            Diff_Report['ASA_Show_Failover'] = {'Status': 'Passed', 'Type' : 'ASA_Show_Failover rank did not change.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Failover']['MyRank'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Failover']['MyRank']}
        else:
            Diff_Report['ASA_Show_Failover'] = {'Status': 'Failed', 'Type' : 'ASA_Show_Failover rank changed.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_Failover']['MyRank'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_Failover']['MyRank']}
        

    if 'ASA_Show_DHCP' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_DHCP' in PostCheck['Extracted_Data'].keys():
        if 'ASA_Show_DHCP' not in Diff_Report.keys():
                Diff_Report['ASA_Show_DHCP'] = {}        
        for ipadd, details in PreCheck['Extracted_Data']['ASA_Show_DHCP'].items():
            if ipadd in PostCheck['Extracted_Data']['ASA_Show_DHCP'].keys():
                if ipadd not in Diff_Report.keys():
                    Diff_Report['ASA_Show_Failover'][ipadd] = {}                        
                if PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State'] == PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State']:
                    Diff_Report['ASA_Show_Failover'][ipadd]['State'] = {'Status': 'Passed', 'Type' : 'ASA_Show_Failover state did not change.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State']}
                else:
                    Diff_Report['ASA_Show_Failover'][ipadd]['State'] = {'Status': 'Failed', 'Type' : 'ASA_Show_Failover state changed.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['State']}

                if PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType'] == PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType']:                    
                    Diff_Report['ASA_Show_Failover'][ipadd]['LType'] = {'Status': 'Passed', 'Type' : 'ASA_Show_Failover state did not change.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType']}
                else:
                    Diff_Report['ASA_Show_Failover'][ipadd]['LType'] = {'Status': 'Failed', 'Type' : 'ASA_Show_Failover state changed.', 'Pre-Value':  PreCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType'], 'Post-Value': PostCheck['Extracted_Data']['ASA_Show_DHCP'][ipadd]['LType']}


    if 'ASA_Show_WebVPN' in PreCheck['Extracted_Data'].keys() and 'ASA_Show_WebVPN' in PostCheck['Extracted_Data'].keys():
        pass

    # except Exception as err:
    #     msg = '[{0}] Error Comparing HealthCheck commands. : {1}'.format('Compare', err)
    #     print(msg)
    #     errorLog.write(msg)   
    return Diff_Report

#	###############################################################################################
#	##################### Output Parsing functions ################################################
#	###############################################################################################
def Parse_ASA_Show_Failover(row,data): 
    return_dict = {}  
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_ASA_Show_Failover'.format(row['LocalIP']),'fg_blue','bg_white'))
    try:
        try:
            mystate = ["".join(x) for x in re.findall(r'This host:\s*-\s*\w*\n\s*(\w*)|This host\s*-\s*\w*\n\s*(\w*)',data,re.MULTILINE)][0]
        except:
            mystate = 'NA'
        try:
            otstate = ["".join(x) for x in re.findall(r'Other host:\s*-\s*\w*\n\s*(\w*)|Other host\s*-\s*\w*\n\s*(\w*)',data,re.MULTILINE)][0]
        except:
            otstate = 'NA'
        try:
            myrank = ["".join(x) for x in re.findall(r'This host:\s*-\s*(\w*)|This host\s*-\s*(\w*)',data,re.MULTILINE)][0]
        except:
            myrank = 'NA'
        try:            
            otrank = ["".join(x) for x in re.findall(r'Other host:\s*-\s*(\w*)|Other host\s*-\s*(\w*)',data,re.MULTILINE)][0]
        except:
            otrank = 'NA'           
        return_dict = {'MyRank' : myrank, 'OtRank': otrank, 'MyState': mystate, 'OtState': otstate}  
    except:
        return_dict = {'MyRank' : 'na', 'OtRank': 'na', 'MyState': 'na', 'OtState': 'na'}  
    return return_dict

def Parse_ASA_Show_DHCP(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_ASA_Show_DHCP'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}  
    for line in data:
        if 'sh' in data or 'IP address' in data or 'Client Identifier' in data:
                continue
        else:
            for x in range(0,15):
                line = re.sub('\ \ ',' ',line.strip()) 
            lines = line.strip().split(' ')
            if len(lines) > 3:          
                ipadd = lines[0]
                cid = lines[1]
                ltype = lines[3]
                return_dict[ipadd] = {'Address' : ipadd, 'CID' : cid, 'State' : state, 'LType' : ltype}
            else:
                continue                       
    return return_dict    

def Parse_ASA_Show_WebVPN(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_ASA_Show_WebVPN'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}      
    if 'Error' in data:
        return_dict['Enabled'] = False
    else: 
        return_dict['Enabled'] = True
    return return_dict

def Parse_ASA_Show_OSPF(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_ASA_Show_OSPF'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}  
    for line in data:
        if 'show ospf neighbor' in data or 'Neighbor ID' in data or 'State' in data:
            continue
        else:
            for x in range(0,15):
                line = re.sub('\ \ ',' ',line.strip())
            lines = line.strip().split(' ')
            if len(lines) > 4:
                neighbor_add = lines[0]
                priority = lines[1]
                state = lines[2]
                zone = lines[5]
                neighbor_ip = lines[4]
                return_dict[neighbor_add] = {'Address' : neighbor_add, 'Priority' : priority, 'State' : state, 'Zone' : zone,  'IP' : neighbor_ip}
            else:
                continue
    return return_dict

def Parse_ASA_Show_IP(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_Show_IP_Add'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    for line in data.split('\n'):
        if 'Interface' in line:
            continue
        else:
            try:
                for x in range(0,15):
                    line = re.sub('\ \ ',' ',line.strip())
                line = re.sub(r'Admin\ Down','AdminDown',line)
                line = re.sub(r'administratively\ down','AdminDown',line)
                lines = line.split(' ')
                if len(lines) < 3:
                    continue
                return_dict[lines[0]] = {'Interface':lines[0],  'ips':lines[1], 'Admin':lines[4],'Oper':lines[5]}
            except:
                continue
    return return_dict



def Parse_ASA_Show_Context(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_Show_Context'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    try:
        context = re.findall(r'Invalid input',data,RE.MULTILINE)[0]
        return False
    except:
        if '*' in data:
            for line in data.split('\n'):
                for x in range(0,15):
                    line = re.sub('\ \ ',' ',line.strip())
                lines = line.strip().split(' ')
                return_dict['Context'] = {'Context':lines[0], 'Class':line[1], 'Interface':line[2], 'Mode':line[3], 'Url':line[4]}   
        else:
            return False
    return return_dict


def Parse_ASA_Show_Ver(row,data): 
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_Show_Ver'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    return_dict['FW_Version'] = re.findall(r'Cisco Adaptive Security Appliance Software Version\s(\S)\s',data,re.MULTILINE)
    return return_dict

def Parse_Show_IP_Int(row,data):
    return_dict = {}
    return_dict[row['name']] = {}
    print(Paint_SVAR('[ {0} - Healthchecks] Parse_Show_IP_Int'.format(row['LocalIP']),'fg_blue','bg_white'))
    for line in data.split('\n'):
        if 'Interface' in line:
            continue
        for x in range(0,15):
            line = re.sub('\ \ ',' ',line.strip())
        lines = line.strip().split(' ')
        if len(lines) > 4:
            interface = lines[0]
            ipadd = lines[1]
            admin = lines[2]
            oper = lines[3]
            return_dict[interface] = {'Interface' : interface, 'State': oper, 'Admin': admin, 'ips':ipadd }
        else:
            continue
    return return_dict

def Check_Show_Ver_for_BUNDLE(row,data,stack):
    bundles  =  ["".join(x) for x in re.findall(r'Bundle|BUNDLE|bundle',data,re.MULTILINE)]
    if len(bundles) == len(stack):
        return True
    else:
        return False

def Parse_Show_Switch(row,data): 
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Switch'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    # print(data)
    extracted_data = ["".join(x) for x in re.findall(r'^\d? .*$|\*\d? .*$',data,re.MULTILINE)]
    # print(extracted_data)
    for line in extracted_data:
        for x in range(0,15):
            line = re.sub('\ \ ',' ',line.strip())
        line = line.split(' ')
        if len(line) < 4:
            continue
        if 'Built-in' in line[1]:
            Switch_num = line[0]
            Switch_state = line[2]
            return_dict[Switch_num] = {'Switch_num': Switch_num,'Switch_mac':line[1], 'Switch_state':Switch_state}        
        else:
            Switch_num = line[0]
            Switch_mac = line[1]
            Switch_state = line[5]
            return_dict[Switch_num] = {'Switch_num': Switch_num, 'Switch_mac':Switch_mac, 'Switch_state':Switch_state}
    return return_dict

def Gen_Stack_List(row,data):
    stack_list = []
    data = Parse_Show_Switch(row,data)
    sw_master = None
    # print(data)
    for sw_num, data in data.items():
        if '*' in sw_num:
            sw_master = re.findall(r'\d',sw_num)[0]
        sw_num = re.findall(r'\d',sw_num)[0]
        stack_list.append(sw_num)
    return stack_list,sw_master

def Parse_Show_Module(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Module'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    extracted_data = re.findall(r'^\d *$',data)

    for line in extracted_data.split('\n'):
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line)
            line = line.split(' ')

            if len(re.findall(r'\d?$',line[1])) >= 1:
                Mod_num = line[0]
                Mod_status = line[5]
                if Mod_num not in return_dict.keys():
                    return_dict[Mod_num] = {}
                    return_dict[Mod_num]['Mod_num'] = Mod_num
                return_dict[Mod_num]['Mod_status'] = Mod_status
            
            elif len(re.findall(r'\d\.\d.*?$',line[1])) >= 1:
                Mod_num = line[0]
                Mod_FW = line[1]
                if Mod_num not in return_dict.keys():
                    return_dict[Mod_num] = {}
                    return_dict[Mod_num]['Mod_num'] = Mod_num
                return_dict[Mod_num]['Mod_FW'] = Mod_FW
            
            elif len(re.findall(r'^\w{4}\.\w{4}\.\w{4}.*?$',line[1])) >= 1:   
                Mod_MAC_start = line[1]
                Mod_MAC_end = line[3]
                Mod_Serial = line[4]
                if Mod_num not in return_dict.keys():
                    return_dict[Mod_num] = {}
                    return_dict[Mod_num]['Mod_num'] = Mod_num
                return_dict[Mod_num]['Mod_MAC_start'] = Mod_MAC_start
                return_dict[Mod_num]['Mod_MAC_end'] = Mod_MAC_end
                return_dict[Mod_num]['Mod_Serial'] = Mod_Serial

    return return_dict                                  

def Parse_ASA_Show_Dir(row,data):
    print(Paint_SVAR('[ {0} - Device Survey] Parse_Show_DIR'.format(row['LocalIP']),'fg_blue','bg_white'))
    try:
        available = re.findall(r'\((\d)\sbytes free',data)
    except:
        available = 'NA'
    try:
        total = re.findall(r'\d*\sbytes total',data)
    except:
        total = 'NA'        
    return {'Total' : total, 'Available' : available}

def Parse_Show_Redundandcy(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Redundandcy'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    return_dict['Uptime'] = re.findall(r'Available system uptime = (.*$)',data,re.MULTILINE)[0]
    return_dict['SwitchoverCount'] = re.findall(r'Switchovers system experienced = (.*$)',data,re.MULTILINE)[0]
    return_dict['ActiveSlot'] = re.findall(r'Active Location = (.*$)',data,re.MULTILINE)[0]
    return_dict['CurrentState'] = re.findall(r'Current Software state = ACTIVE (.*$)',data,re.MULTILINE)[0]
    return_dict['SW_Uptime'] = re.findall(r'Uptime in current state = (.*$)',data,re.MULTILINE)[0]
    return return_dict

def Parse_Show_platform(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_platform'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    
    for line in data.split('\n'):
        if 'Slot' in line or '---' in line:
            continue
        line = re.sub('\ \,',',',line)
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line)
        line = line.split(' ')
        Slot = line[0]
        if Slot in return_dict.keys():
            pass
        else:
            return_dict[Slot] = {}
        if len(line) == 4:
            
            return_dict[Slot]['Type'] = line[1]
            return_dict[Slot]['State']  = line[2]
            return_dict[Slot]['Insert_Time']  = line[3]
        elif len(line) == 3:        
            return_dict[Slot]['CPLD_Ver'] = line[1]
            return_dict[Slot]['FW_Ver'] = line[2]
    return return_dict

def Parse_Show_bootvar(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_bootvar'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    return_dict['Master'] = {}
    return_dict['Backup'] = {}
    try:
        return_dict['Master']['BootVar']  =  ["".join(x) for x in re.findall(r'BOOT path-list *: (.*)$|BOOT variable =  (.*)$|BOOT variable = (.*)$',data,re.MULTILINE)][0]
    except:
        return_dict['Master']['BootVar']  = 'Not Present'
    try:
        return_dict['Master']['Config']  =  ["".join(x) for x in re.findall(r'Config file *: (.*)$|CONFIG_FILE variable = (.*)$',data,re.MULTILINE)][0]
        return_dict['Master']['BootLDR']  =  ["".join(x) for x in re.findall(r'BOOT path-list *: (.*)$|BOOTLDR variable = (.*)$',data,re.MULTILINE)][0]
    except:
        return_dict['Master']['Config']  =  'Not Present'
        return_dict['Master']['BootLDR']  = 'Not Present'
    if 'BOOTLDR' in data:
        return_dict['Master']['ConfigReg']  =  ["".join(x) for x in re.findall(r'BOOT path-list *: (.*)$|Configuration register is (.*)$',data,re.MULTILINE)][0]

    if 'Standby' in data:
        return_dict['Backup']['BootVar']  = re.findall(r'Standby BOOT variable =  (.*)$',data,re.MULTILINE)[0]
        return_dict['Backup']['Config']  = re.findall(r'Standby CONFIG_FILE variable = (.*)$',data,re.MULTILINE)[0]
        return_dict['Backup']['BootLDR']  = re.findall(r'Standby BOOTLDR variable = (.*)$',data,re.MULTILINE)[0]
        return_dict['Backup']['ConfigReg']  = re.findall(r'Standby Configuration register is (.*)$',data,re.MULTILINE)[0]

    return return_dict    

def Parse_Show_CDP(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_CDP'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    for line in data.split('\n'):
        if 'Device ID' in line or 'Router' in line or 'Switch' in line or 'Remote' in line or ',' in line or len(line) < 2:
            continue
        line = re.sub(r'Fas\s','Fas',line)
        line = re.sub(r'Gig\s','Gig',line)
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line)
        line = line.strip().split(' ')
        if len(line) == 1:
            remote_dev = line[0]
            if line[0] not in return_dict.keys():
                return_dict[line[0]] = {}
        else:
            if 'Gig' in line[0] or 'Fas' in line[0]:
                return_dict[remote_dev]['Local Interface'] = line[0]
            else:
                if line[0] not in return_dict.keys():
                    return_dict[line[0]] = {}
                    remote_dev = line[0]
                return_dict[remote_dev]['Local Interface'] = line[1]
            return_dict[remote_dev]['Remote Interface'] = line[len(line) -1 ]
            return_dict[remote_dev]['Platform'] = line[len(line) - 2 ]
    return return_dict     

def Parse_Show_Route_Summary(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Route_Summary'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    Total = 0
    for x in range(0,33):
        cidr = '/{0} :'.format(x)
        cidr_re = '/{0} : (.*) '
        cidr_re = re.compile(cidr_re)
        if  cidr in data:
            return_dict[cidr]  = re.findall(cidr_re,data,re.MULTILINE)[0]
    for cidr,data in return_dict.items():
        Total += int(data)
    return_dict['Total'] = Total
    return return_dict

def Parse_Show_Spanning_Tree(row,data):    
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Spanning_Tree'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    for line in data.split('\n'):
        if 'VLAN' in line:
            VLAN = line
            if VLAN not in return_dict.keys():
                return_dict[VLAN] = {}
        elif 'Root ID' in line:
            return_dict[VLAN]['Root_Pri'] = re.findall(r'Root ID\s*Priority\s*(.*) ',data,re.MULTILINE)[0]
        elif 'Hello Time' in line:
            return_dict[VLAN]['Hello'] = re.findall(r'Hello Time\s*(.*) ',data,re.MULTILINE)[0]
            return_dict[VLAN]['Max_Age'] = re.findall(r'Max Age\s*(.*) ',data,re.MULTILINE)[0]
            return_dict[VLAN]['Forward_Delay'] = re.findall(r'Forward Delay\s*(.*) ',data,re.MULTILINE)[0]
        elif 'Interface' in line:
            continue
        line = re.sub(r'\*',' ',line)
        line = line.split(' ')
        if len(line) == 7:
            if line[0] not in return_dict[VLAN].keys():
                return_dict[VLAN][line[0]] = {}
            return_dict[VLAN][line[0]]['Role'] = line[1]
            return_dict[VLAN][line[0]]['FWD_State'] = line[2]
            return_dict[VLAN][line[0]]['N_Type'] = line[5]
            return_dict[VLAN][line[0]]['P2P'] = line[6]
    return return_dict        

def Parse_Show_EIGRP_Neighbors(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_EIGRP_Neighbors'.format(row['LocalIP']),'fg_blue','bg_white'))
    # print(data)
    return_dict = {}
    for line in data.split('\n'):
        if 'IP-EIGRP' in line or 'H   Address' in line:
            continue
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line)            
        line = line.split(' ')

        if len(line) == 8:
            Address = line[1]
            if Address not in return_dict.keys():
                return_dict[Address] = {}
            return_dict[Address]['Interface'] = line[2]
            return_dict[Address]['Uptime'] = line[4]
            return_dict[Address]['SRTT'] = line[5]
            return_dict[Address]['RTO'] = line[6]
        
    return return_dict        

def Parse_Show_ARP(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_ARP'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    for line in data.split('\n'):
        if 'Total number' in line or 'IP ARP ' in line or 'Address' in line or len(line) <=2:
            continue
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.split(' ')
        if line[1] not in return_dict.keys():
            return_dict[line[1]] = {}
        return_dict[line[1]]['Age'] = line[2]
        return_dict[line[1]]['MAC'] = line[3]
        return_dict[line[1]]['Interface'] = line[4]
    return return_dict        

def Parse_Show_MAC(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_MAC'.format(row['LocalIP']),'fg_blue','bg_white'))
    # print(data)
    return_dict = {}

    return_dict['static'] = {}
    return_dict['dynamic'] = {}

    static = re.findall(r'^.* STATIC .*$',data,re.MULTILINE)
    dynamic = re.findall(r'^.* DYNAMIC .*$',data,re.MULTILINE)

    for line in static:
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.strip().split(' ')
        if line[1] not in return_dict['static'].keys():
            return_dict['static'][line[1]] = {}
        return_dict['static'][line[1]]['vlans'] = line[0]
        return_dict['static'][line[1]]['ports'] = line[3]

    for line in dynamic:
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.split(' ')
        if line[1] not in return_dict['dynamic'].keys():
            return_dict['dynamic'][line[1]] = {}
        return_dict['dynamic'][line[1]]['vlans'] = line[0]
        return_dict['dynamic'][line[1]]['ports'] = line[3]
    
    return return_dict

def Parse_Show_EtherChannel(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_EtherChannel'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    return_dict['Total_Groups'] = re.findall(r'Number of channel-groups in use: (.*)$',data,re.MULTILINE)[0]
    for line in data.split('\n'):
        if '-' in line or ':' in line:
            continue
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.split(' ')
        if len(re.findall(r'\d',line[0])) > 0:
            if line[0] not in return_dict.keys():
                port = line[1]
                return_dict[port] = {}
            return_dict[port]['protocol'] = line[2]
            for x in range(2,len(line) - 1):
                if 'Ports' not in return_dict[port].keys():
                    return_dict[port]['Ports'] = [line[x]]
                else:
                    return_dict[port]['Ports'].append(line[x])
        else:
            for x in range(2,len(line) - 1):
                if 'Ports' not in return_dict[port].keys():
                    return_dict[port]['Ports'] = [line[x]]
                else:
                    return_dict[port]['Ports'].append(line[x])
    return return_dict

def Parse_Show_Int_Status(row,data,vlans):
    
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Int_Status'.format(row['LocalIP']),'fg_blue','bg_white'))
    # print(data)
    vlans = Parse_Show_VLAN(row,vlans)
    return_dict = {}
    data = re.sub(r'No\ ','No',data)

    for line in data.split('\n'):
        thisline = line
        if 'Speed' in line:
            header = line
            continue

        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.split(' ')
        
        if len(line) < 6:
            continue
        if ',' in line[len(line) - 4 ]:
            temp = line[len(line) - 4 ].split(',')[0]
            line[len(line) - 4 ] = temp
        if ',' in line[len(line) - 5 ]:
            temp = line[len(line) - 5 ].split(',')[0]
            line[len(line) - 5 ] = temp
        if line[0] not in return_dict.keys():
            return_dict[line[0]] = {}
        
        return_dict[line[0]]['Name'] = line[1]
        if 'disabled' in line[1] or 'connect' in line[1] or 'notconnect' in line[1]:
            return_dict[line[0]]['State'] = line[1]
            return_dict[line[0]]['Vlan'] = line[2]
            if line[2] != 'trunk':
                if line[len(line) - 4] in ['full','a-full','half','a-half','auto']:
                    return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 5]]
                else:
                    return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 4]]
            else:
                return_dict[line[0]]['Vlan_Name'] = 'trunk'
            return_dict[line[0]]['Duplex'] = line[3]
            return_dict[line[0]]['Speed'] = line[4]
            return_dict[line[0]]['Type'] = line[5]    
            return_dict[line[0]]['RAW'] = thisline
            return_dict[line[0]]['Header'] = header
        else:
            return_dict[line[0]]['State'] = line[2]
            return_dict[line[0]]['Vlan'] = line[len(line) - 4]
            if line[len(line) - 4] != 'trunk':
                if line[len(line) - 4] != 'unassigned':
                    if line[len(line) - 4] in ['auto','full','a-full','half','a-half']:                         
                        if line[len(line) - 5] != 'unassigned' and line[len(line) - 5] != 'trunk':
                            # print('vlans:' + vlans[line[len(line) - 5]] )  
                            return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 5]]
                        else:
                            return_dict[line[0]]['Vlan_Name'] = 'unassigned'
                    elif line[len(line) - 3] in ['auto','full','a-full','half','a-half']:                         
                        if line[len(line) - 4] != 'unassigned' and line[len(line) - 4] != 'trunk':
                            # print('vlans:' + vlans[line[len(line) - 4]] )  
                            return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 4]]
                    elif line[len(line) - 2 ] in ['auto','full','a-full','half','a-half']:
                        if line[len(line) - 3] != 'unassigned' and line[len(line) - 3] != 'trunk':
                            # print('vlans:' + vlans[line[len(line) - 3]] )  
                            return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 3]]                        
                    else:
                        # print(line)
                        return_dict[line[0]]['Vlan_Name'] = vlans[line[len(line) - 4]]
                else:
                    return_dict[line[0]]['Vlan_Name'] = 'unassigned'                    
            else:
                return_dict[line[0]]['Vlan_Name'] = 'trunk'            
            return_dict[line[0]]['Duplex'] = [len(line) - 3]
            return_dict[line[0]]['Speed'] = [len(line) - 2]
            return_dict[line[0]]['Type'] = [len(line) - 1]
            return_dict[line[0]]['RAW'] = thisline
            return_dict[line[0]]['Header'] = header
    return return_dict       

def Parse_Show_Inv(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Inv'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    Names =   ["".join(x) for x in re.findall(r'NAME: (.*),|NAME: \"(.*)\"',data,re.MULTILINE)]
    Descs =  ["".join(x) for x in re.findall(r'DESCR: (.*)|DESCR: \"(.*)\"',data,re.MULTILINE)]
    PIDs =  ["".join(x) for x in re.findall(r'PID: (.*)\s,|PID: "(.*)"\s,',data,re.MULTILINE)]
    VIDs =  ["".join(x) for x in re.findall(r'VID: (.*)\s,|VID: "(.*)"\s,',data,re.MULTILINE)]
    SNs =  ["".join(x) for x in re.findall(r'SN: (.*)|SN: "(.*)"',data,re.MULTILINE)]
    for x in range(0,len(Descs)):
        if x not in return_dict.keys():
            return_dict[x] = {}
        return_dict[x]['Name'] = re.sub('\"','',str(Names[x]).strip().split(' ')[0])
        return_dict[x]['Desc'] = re.sub('\"','',str(Descs[x]).strip().split(' ')[0])
        return_dict[x]['PID'] = re.sub('\"','',str(PIDs[x]).strip().split(' ')[0])
        return_dict[x]['VID'] = VIDs[x]
        return_dict[x]['SN'] = SNs[x]
    return return_dict       

def Parse_Show_Env(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Env'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    return_dict['Modules'] = {}
    try:
        return_dict['FAN'] = re.findall(r'FAN is (\S+)',data,re.MULTILINE)[0]
    except:
        return_dict['FAN'] = 'null'
    return_dict['TEMP_STATE'] = re.findall(r'TEMPERATURE is (\S+)',data,re.MULTILINE)[0]
    try:
        return_dict['TEMP'] = re.findall(r'FAN is (\S+)',data,re.MULTILINE)[0]
    except:
        return_dict['TEMP'] = 'null'
    process_list = ["".join(x) for x in re.findall(r'^\d .*$|^ \d .*$',data,re.MULTILINE)]
    y = 0
    for line in process_list:
        if 'Not Present' in line:
            continue
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.strip().split(' ')
        if line[0] not in return_dict['Modules'].keys():
            return_dict['Modules'][line[0]] = {}
        if y < (len(process_list)/2):
            return_dict['Modules'][line[0]]['Mod_Num'] = line[0]
            return_dict['Modules'][line[0]]['PID'] = line[1]
            if len(line) == 3:
                return_dict['Modules'][line[0]]['Power'] = line[2]
            else:
                return_dict['Modules'][line[0]]['Serial'] = line[2]
                return_dict['Modules'][line[0]]['Status'] = line[3]
                return_dict['Modules'][line[0]]['Power'] = line[4]
        else:
            if len(line) > 3:
                return_dict['Modules'][line[0]]['RPS_Status'] = line[1]
                return_dict['Modules'][line[0]]['RPS_Name'] = line[2]
                return_dict['Modules'][line[0]]['RPS_Serial'] = line[3]
                return_dict['Modules'][line[0]]['RPS_Port'] = line[4]
        y += 1
    return return_dict       

def Parse_Show_VLAN(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_VLAN'.format(row['LocalIP']),'fg_blue','bg_white'))
    return_dict = {}
    for line in data.split('\n'):
        if 'Status' in line or 'Type' in line or '--' in line:
            continue
        for x in range(0,10):
            line = re.sub('\ \ ',' ',line) 
        line = line.strip().split(' ')
        if len(line) < 3:
            continue
        if 'enet' in line[1] or 'fd' in line[1] or 'tr' in line[1]:
            continue
        else:
            if 'act' in line[1]:
                return_dict[line[0]] = 'None'
            else:
                return_dict[line[0]] = line[1]
        return_dict['routed'] = 'routed'
    return return_dict


def Parse_Show_Run_Int(row,data):
    print(Paint_SVAR('[ {0} - HealthChecks] Parse_Show_Run_Int'.format(row['LocalIP']),'fg_blue','bg_white'))
    # print (data)
    return_dict = {}
    capture = False
    for line in data.split('\n'):
        if len(re.findall(r'^interface',line)) > 0:
            capture = True
            interface = line.split(' ')[1]
            interface = re.sub('FastEthernet', 'Fa',interface)    
            interface = re.sub('GigabitEthernet', 'Gi',interface)
            return_dict[interface] = line
            continue
        if capture == True:
            if '!' in line:
                capture = False
                continue
            else:
                return_dict[interface] = return_dict[interface] + '\n' + line
    return return_dict


def Parse_Show_Lic(row,data):
    return_dict = {}
    for switch in data:
        return_dict[switch] = {}
        try:
            return_dict[switch]['Feature'] =   ["".join(x) for x in re.findall(r'Feature: (.*),| Feature: \"(.*)\"',data,re.MULTILINE)]
            return_dict[switch]['License_Type'] =   ["".join(x) for x in re.findall(r'License Type: (.*),| License Type: \"(.*)\"',data,re.MULTILINE)]
            return_dict[switch]['License_State'] =   ["".join(x) for x in re.findall(r'License State: (.*),| License State: \"(.*)\"',data,re.MULTILINE)]
            return_dict[switch]['License_Priority'] =   ["".join(x) for x in re.findall(r'License Priority: (.*),| License Priority: \"(.*)\"',data,re.MULTILINE)]
        except:
            pass
    return return_dict


def file_size(file_path):
    """
    this function will return the file size
    """
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return file_info.st_size

def Compile_Report(host,data):
    report = ''
    for item, results in data.items():
        print(Paint_SVAR('[ {1} - Report] Command - {0}'.format(item,host),'fg_blue','bg_white'))
        report = report + '\n' + 'Command - {0}'.format(item,host)
        if 'Status' in data[item].keys():
            if results['Status'] == 'Failed':
                highlight = 'fg_red'
            elif results['Status'] == 'Passed':
                highlight = 'fg_green'
            else:
                highlight = 'fg_blue'
            # print(Paint_SVAR('[Report] Command - {0}'.format(item),highlight,'bg_white'))
            print(Paint_SVAR('[ {2} - Report] Status: {0} | Type: {1}'.format(results['Status'],results['Type'],host),highlight,'bg_white'))
            # report = report + '\n' + 'Command - {0}'.format(item)
            report = report + '\n' + '[ {2} - Report] Status: {0} | Type: {1}'.format(results['Status'],results['Type'],host)
        else:
            for section, details in data[item].items():
                if len(details.keys()) > 0:
                    print(Paint_SVAR('[ {1} - Report] Section - {0}'.format(section,host),'fg_blue','bg_white'))
                    report = report + '\n' + 'Section - {0}'.format(section,host)
                if 'Status' in details.keys():
                    if details['Status'] == 'Failed':
                        highlight = 'fg_red'
                    elif details['Status'] == 'Passed':
                        highlight = 'fg_green'
                    else:
                        highlight = 'fg_blue'
                    # print(Paint_SVAR('[Report] Command - {0}'.format(item),highlight,'bg_white'))

                    print(Paint_SVAR('[ {2} - Report] Status: {0} | Type: {1}'.format(details['Status'],details['Type'],host),highlight,'bg_white'))
                    if 'Config' in details.keys():
                        print(Paint_SVAR('[ {2} - Report] Status: {0} | Type: {1}'.format(details['Status'],details['Type'],host),'fg_blue','bg_white'))
                    # report = report + '\n' + 'Command - {0}'.format(item)
                    
                    report = report + '\n' + 'Details - {0}'.format(str(details))
                    if 'Config' in details.keys():
                        report = report + '\n' + '[Report] Config - \n{0}'.format(details['Config'])                        
                else: 
                    # print(Paint_SVAR('[Report] Command - {0}'.format(item),highlight,'bg_white'))
                    # print(Paint_SVAR('[Report] Section - {0}'.format(section),highlight,'bg_white'))
                    # report = report + '\n' + 'Command - {0}'.format(item)
                    # report = report + '\n' + 'Section - {0}'.format(section)
                    detail_count = 1
                    for item2,details2 in details.items():
                        if 'Status' in details2.keys():
                            if details2['Status'] == 'Failed':
                                highlight = 'fg_red'
                            elif details2['Status'] == 'Passed':
                                highlight = 'fg_green'
                            else:
                                highlight = 'fg_blue'

                            print(Paint_SVAR('[ {3} - Report] Section: {0} | Status : {1} | Type {2}'.format(item2,details2['Status'],details2['Type'],host),highlight,'bg_white'))
                            report = report + '\n' + '[ {3} - Report] Section: {0} | Status : {1} | Type {2}'.format(item2,details2['Status'],details2['Type'],host)
                            if 'Config' in details2.keys() and detail_count == len(details.keys()):
                                print(Paint_SVAR('[ {1} - Report] Config - \n{0}'.format(details2['Config'],host),'fg_blue','bg_white'))
                                report = report + '\n' + '[Report] Config - \n{0}'.format(details2['Config'])
                                
                            if details2['Status'] == 'Failed' and detail_count == len(details.keys()):
                                if 'Header' in details2.keys() and 'Pre-RAW' in details2.keys():
                                    print(Paint_SVAR('[ {0} - Report] Pre-Check - '.format(host),'fg_blue','bg_white'))
                                    print(Paint_SVAR('{0}'.format(details2['Header'],host),'fg_blue','bg_white'))
                                    print(Paint_SVAR('{0}'.format(details2['Pre-RAW'],host),'fg_red','bg_white'))
                                    print(Paint_SVAR('[ {0} - Report] Post-Check - '.format(host),'fg_blue','bg_white'))
                                    print(Paint_SVAR('{0}'.format(details2['Header'],host),'fg_blue','bg_white'))
                                    print(Paint_SVAR('{0}'.format(details2['Post-RAW'],host),'fg_red','bg_white'))
                                    report = report + '\n' + '[ {0} - Report] Pre-Check - \n'.format(host)
                                    report = report + '\n' + '{0}'.format(details2['Header'],host)
                                    report = report + '\n' + '{0}'.format(details2['Pre-RAW'],host)
                                    report = report + '\n' + '[ {0} - Report] Post-Check - \n'.format(host)
                                    report = report + '\n' + '{0}'.format(details2['Header'],host)
                                    report = report + '\n' + '{0}'.format(details2['Post-RAW'],host)                                    
                                    Print_Details = False
                            detail_count += 1
                        else:
                            for item3, details3 in details2.items():
                                if 'Status' in details3.keys():
                                    if details2['Status'] == 'Failed':
                                        highlight = 'fg_red'
                                    elif details2['Status'] == 'Passed':
                                        highlight = 'fg_green'
                                    else:
                                        highlight = 'fg_blue'

                                    print(Paint_SVAR('[ {3} - Report] Section: {0} | Status : {1} | Type {2}'.format(item3,details3['Status'],details3['Type'],host),highlight,'bg_white'))
                                    report = report + '\n' + '[ {3} - Report] Section: {0} | Status : {1} | Type {2}'.format(item3,details3['Status'],details3['Type'],host)

    report_fn = '{0}_Healthcheck_Report_{1}.txt'.format(host,current_date)
    with open(report_fn,'w+') as report_fh:
        report_fh.write(report)
    
    return report   


def Write_RAW_Report(host,data,prepost):
    report_out = ''
    report_order = sorted(data['Raw_Data'].keys())
    for item in report_order:
        report_out += '\n {0}'.format(data['Raw_Data'][item])
    report_fn = '{0}_{1}Healthcheck_Raw_{2}.txt'.format(host,prepost,current_date)
    with open(report_fn,'w+') as report_fh:
        report_fh.write(report_out)
    

#	###############################################################################################
#	##################### MultiThread with return class ###########################################
#	###############################################################################################

class ThreadWithReturn(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._return = None

    def run(self):
        target = getattr(self, _thread_target_key)
        if not target is None:
            self._return = target(*getattr(self, _thread_args_key))

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        # print self._return
        return self._return   



#	###############################################################################################
#	##################### ANSI Color functions ####################################################
#	###############################################################################################

		
def Paint_Brush(Selected_Color):
	Selected_Color = Selected_Color.lower()
	if Selected_Color == 'reset':
		reset='\033[0m'
		return reset
	if Selected_Color == 'bold':
		bold='\033[1m'
		return bold
	if Selected_Color == 'italics':
		italics='\033[3m'
		return italics
	if Selected_Color == 'underline':	
		underline='\033[4m'
		return underline
	if Selected_Color == 'inverse':	
		inverse='\033[7m'
		return inverse
	if Selected_Color == 'strikethrough':	
		strikethrough='\033[9m'
		return strikethrough
	if Selected_Color == 'bold_off':	
		bold_off='\033[22m'
		return bold_off
	if Selected_Color == 'italics_off':	
		italics_off='\033[23m'
		return italics_off
	if Selected_Color == 'underline_off':	
		underline_off='\033[24m'
		return underline_off
	if Selected_Color == 'inverse_off':	
		inverse_off='\033[27m'
		return inverse_off
	if Selected_Color == 'strikethrough_off':	
		strikethrough_off='\033[29m'
		return strikethrough_off
	if Selected_Color == 'fg_black':		
		fg_black='\033[30m'
		return fg_black
	if Selected_Color == 'fg_red':		
		fg_red='\033[31m'
		return fg_red
	if Selected_Color == 'fg_green':		
		fg_green='\033[32m'
		return fg_green
	if Selected_Color == 'fg_yellow':		
		fg_yellow='\033[33m'
		return fg_yellow
	if Selected_Color == 'fg_blue':		
		fg_blue='\033[34m'
		return fg_blue
	if Selected_Color == 'fg_magenta':		
		fg_magenta='\033[35m'
		return fg_magenta
	if Selected_Color == 'fg_cyan':		
		fg_cyan='\033[36m'
		return fg_cyan
	if Selected_Color == 'fg_white':		
		fg_white='\033[37m'
		return fg_white
	if Selected_Color == 'fg_default':		
		fg_default='\033[39m'
		return fg_default
	if Selected_Color == 'bg_black':		
		bg_black='\033[40m'
		return bg_black
	if Selected_Color == 'bg_red':		
		bg_red='\033[41m'
		return bg_red
	if Selected_Color == 'bg_green':		
		bg_green='\033[42m'
		return bg_green
	if Selected_Color == 'bg_yellow':		
		bg_yellow='\033[43m'
		return bg_yellow
	if Selected_Color == 'bg_blue':				
		bg_blue='\033[44m'
		return bg_blue
	if Selected_Color == 'bg_magenta':		
		bg_magenta='\033[45m'
		return bg_magenta
	if Selected_Color == 'bg_cyan':		
		bg_cyan='\033[46m'
		return bg_cyan
	if Selected_Color == 'bg_white':		
		bg_white='\033[47m'
		return bg_white
	if Selected_Color == 'bg_default':		
		bg_default='\033[49m'
		return bg_default
	else: 
		bg_default='\033[49m'
		return bg_default

	return 

def Paint_SVAR(SVAR,FGC,BGC,reset=True):
    if reset == True:
	    SVAR_MOD='{0}{1}{2}{3}'.format(Paint_Brush(FGC),Paint_Brush(BGC),SVAR,Paint_Brush('reset'))
    else:
        SVAR_MOD='{0}{1}{2}'.format(Paint_Brush(FGC),Paint_Brush(BGC),SVAR,Paint_Brush('reset'))
    return SVAR_MOD
			
main()