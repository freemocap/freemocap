##
##
##  ███████ ███    ███  ██████     ███████ ███████ ███████ ███████ ██  ██████  ███    ██ 
##  ██      ████  ████ ██          ██      ██      ██      ██      ██ ██    ██ ████   ██ 
##  █████   ██ ████ ██ ██          ███████ █████   ███████ ███████ ██ ██    ██ ██ ██  ██ 
##  ██      ██  ██  ██ ██               ██ ██           ██      ██ ██ ██    ██ ██  ██ ██ 
##  ██      ██      ██  ██████     ███████ ███████ ███████ ███████ ██  ██████  ██   ████ 
##                                                                                       
## https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=FMC%20Session

from FMC_MultiCamera import FMC_MultiCamera
import datetime
from pathlib import Path

from rich import print, inspect
from rich.console import Console
rich_console = Console()


class FMC_Session:
    ## 
    ## 
    ##                 ██ ███    ██ ██ ████████                 
    ##                 ██ ████   ██ ██    ██                    
    ##                 ██ ██ ██  ██ ██    ██                    
    ##                 ██ ██  ██ ██ ██    ██                    
    ## ███████ ███████ ██ ██   ████ ██    ██    ███████ ███████ 
    ##                                                          
    ## 

    def __init_(self):
        
        self.sessionID = datetime.datetime.now().strftime("FreeMoCap_Session_%Y-%b-%d_%H_%M_%S")
        self.save_path = Path('data/' + self._rec_name)
        self.save_path.mkdir(parents=True)
        self.path_to_log_file = Path(str(self.save_path / self.sessionID) + '_log.txt')
    
    def start(self):
        self.multi_cam = FMC_MultiCamera(show_multi_cam_stream=False )
        self.multi_cam.start()    
        while not self.multi_cam.exit_event.is_set():   
            if not self.multi_cam.multi_cam_tuple_queue.empty():
                multi_cam_image = self.multi_cam.multi_cam_tuple_queue.get()
                rich_console.log('FMC_Session - Grabbed a multi_cam_image - queue size: {}'.format(self.multi_cam.multi_cam_tuple_queue.qsize()))
    ###         
    ### ███████ ████████  ██████              
    ### ██         ██    ██                   
    ### █████      ██    ██                   
    ### ██         ██    ██                   
    ### ███████    ██     ██████     ██ ██ ██ 
    ###                                       
    
    def __enter__(self):
        """Context manager -  No need to do anything special on start"""
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Context manager -  no need to do anything special on stop (maybe set 'exit_event?" """
        return self

###   
###               
###   ██ ███████                     ███    ███  █████  ██ ███    ██                 
###   ██ ██                          ████  ████ ██   ██ ██ ████   ██                 
###   ██ █████                       ██ ████ ██ ███████ ██ ██ ██  ██                 
###   ██ ██                          ██  ██  ██ ██   ██ ██ ██  ██ ██                 
###   ██ ██          ███████ ███████ ██      ██ ██   ██ ██ ██   ████ ███████ ███████ 
###                                                                                  
###                                                                                  

if __name__ == "__main__":
    with FMC_Session() as sesh:
        sesh.start()