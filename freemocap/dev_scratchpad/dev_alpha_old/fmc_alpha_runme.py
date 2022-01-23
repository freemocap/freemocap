import freemocap as fmc

from FMC_MultiCamera import FMC_MultiCamera

from pathos.helpers import mp as pathos_mp_helper

if __name__ =='__main__':
    pathos_mp_helper.freeze_support()

    multi_cam =  FMC_MultiCamera(freemocap_data_folder='C:/Users/WindowsPC_Hallway/Dropbox/FreeMoCapProject/FreeMocap_Data')
    sessionID = multi_cam._rec_name
    multi_cam.start(standalone_mode=True)    
    f=9
