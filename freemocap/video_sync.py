import os
import sys
import matplotlib
import moviepy.editor as mp
import librosa
import time
from glob import glob
from matplotlib import pyplot as plt
import numpy as np
from scipy import signal

class VideoSynchTrimming:
    '''Class of functions for time synchronizing and trimming video files based on cross correlaiton of their audio.'''
    
    def __init__(self):
        '''Initialize VideoSynchTrimmingClass'''
        pass

    def get_clip_list(self, base_path, file_type):
        '''Return a list of all video files in the base_path folder that match the given file type.'''

        # change directory to folder containing raw videos
        clip_list = os.listdir(base_path+'/RawVideos')

        # # create general search from file type to use in glob search, including cases for upper and lowercase file types
        # file_extension_upper = '*' + file_type.upper()
        # file_extension_lower = '*' + file_type.lower()
    
        # # make list of all files with file type
        # clip_list = glob(file_extension_upper) + glob(file_extension_lower) #if two capitalization standards are used, the videos may not be in original order
        # os.chdir(base_path)
        return clip_list

    def get_files(self, base_path, clip_list):
        '''Get video files from clip_list, extract the audio, and put the video and audio files in a list.
        Return a list of lists containing the video file name and file, and audio name and file.
        Also return a list containing the audio sample rate from each file.'''
    
        # create empty list for storing audio and video files, will contain sublists formatted like [video_file_name,video_file,audio_file_name,audio_file] 
        file_list = []

        # create empty list to hold audio sample rate, so we can verify samplerate is the same across all audio files
        sample_rate_list = []

        video_path = os.path.join(base_path,"RawVideos")

        audio_path = os.path.join(base_path,"AudioFiles")
        os.makedirs(audio_path, exist_ok=True)

        # iterate through clip_list, open video files and audio files, and store in file_list
        for clip in clip_list:
            # take vid_name and change extension to create audio file name
            vid_name = clip
            audio_name = clip.split(".")[0] + '.wav'
            # open video files
            print(video_path,vid_name)
            video_file = mp.VideoFileClip(os.path.join(video_path,vid_name), audio=True)

            # get length of video clip
            vid_length = video_file.duration

            # create .wav file of clip audio
            video_file.audio.write_audiofile(os.path.join(audio_path,audio_name))

            # extract raw audio from Wav file
            audio_signal, audio_rate = librosa.load(os.path.join(audio_path,audio_name), sr = None)
            sample_rate_list.append(audio_rate)

            # save video and audio file names and files in list
            file_list.append([vid_name, video_file, audio_name, audio_signal])

            # print relevant video and audio info
            print("video length:", vid_length, "seconds", "audio sample rate", audio_rate, "Hz")

        return file_list, sample_rate_list

    def get_fps_list(self, file_list):
        '''Retrieve frames per second of each video clip in file_list'''
        return [file[1].fps for file in file_list]

    def check_rates(self, rate_list):
        '''Check if audio sample rates or audio frame rates are equal, throw an exception if not (or if no rates are given).'''
        if len(rate_list) == 0:
            raise Exception("no rates given")
        else:
            if rate_list.count(rate_list[0]) == len(rate_list):
                print("all rates are equal to", rate_list[0])
                return rate_list[0]
            else:
                raise Exception("rates are not equal")

    def normalize_audio(self, audio_file):
        '''Perform z-score normalization on an audio file and return the normalized audio file - this is best practice for correlating.'''
        return ((audio_file - np.mean(audio_file))/np.std(audio_file - np.mean(audio_file)))

    def cross_correlate(self, audio1, audio2):
        '''Take two audio files, sync them using cross correlation, and trim them to the same length.
        Inputs are two WAV files to be synced. Return the lag expressed in terms of the audio sample rate of the clips'''

        # compute cross correlation with scipy correlate function, which gives the correlation of every different lag value
        # mode='full' makes sure every lag value possible between the two signals is used, and method='fft' uses the fast fourier transform to speed the process up 
        corr = signal.correlate(audio1, audio2, mode='full', method='fft')
        # lags gives the amount of time shift used at each index, corresponding to the index of the correlate output list
        lags = signal.correlation_lags(audio1.size, audio2.size, mode="full")
        # lag is the time shift used at the point of maximum correlation - this is the key value used for shifting our audio/video
        lag = lags[np.argmax(corr)]
    
        print("lag:", lag)

        return lag

    def find_lags(self, file_list, sample_rate):
        '''Take a file list containing video and audio files, as well as the sample rate of the audio, cross correlate the audio files, and output a lag list.
        The lag list is normalized so that the lag of the latest video to start in time is 0, and all other lags are positive'''
        
        lag_list = [self.cross_correlate(file_list[0][3],file[3])/sample_rate for file in file_list] # cross correlates all audio to the first audio file in the list
        #also divides by the audio sample rate in order to get the lag in seconds
        ''' this is a for loop that accomplishes the same as the above list comprehension
        lag_list = []
        for file in file_list:
            # cross correlates all audio to the first audio file in the list
            lag = self.cross_correlate(file_list[0][3],file[3])
            lag_list.append(lag)
        print(lag_list)
        '''

        #now that we have our lag array, we subtract every value in the array from the max value
        #this creates a normalized lag array where the latest video has lag of 0
        #the max value lag represents the latest video - thanks Oliver for figuring this out
        norm_lag_list = [(max(lag_list) - value) for value in lag_list]
        ''' this is a for loop that accomplishes the same as the above list comprehension
        norm_lag_list = []
        for value in lag_list:
            value = max(lag_list) - value #the max value lag represents the latest video - thanks Oliver for figuring this out
            value /= sample_rate #we also divide by the audio sample rate in order to get the lag in seconds
            norm_lag_list.append(value)
        '''
        print("original lag list: ", lag_list, "normalized lag list: ", norm_lag_list)
        # plot lags before and after to make visualization that this is doing what we want
        return norm_lag_list

    def trim_videos(self, file_list, lag_list, base_path):
        # this takes a list of video files and a list of lags, and shortens the beginning of the video by the lags, and trims the ends so they're all the same length
        
        # create new SyncedVideos folder
        synced_path = os.path.join(base_path,"SyncedVideos")
        os.makedirs(synced_path, exist_ok=True)

        # change directory to SyncedVideos folder
        os.chdir(synced_path)
        
        front_trimmed_videos = []

        # for each video in the list, create a new video trimmed from the begining by the lag value for that video, and add it to the empty list
        for i in range(len(file_list)):
            print(file_list[i][1])
            front_trimmed_video = file_list[i][1].subclip(lag_list[i],file_list[i][1].duration)
            front_trimmed_videos.append([file_list[i][0], front_trimmed_video])
        
        print(front_trimmed_videos)

        # now we find the duration of each video and add it to a list to find the shortest video duration
        min_duration = min([video[1].duration for video in front_trimmed_videos])
        ''' this is a for loop that accomplishes the same as the above list comprehension
        # now we find the duration of each video and add it to a list to find the shortest video duration
        duration_list = []
        for video in front_trimmed_videos:
            duration = video[1].duration
            duration_list.append(duration)
        # this is the shortest length of any of the videos, and we trim all videos to this length to ensure they're the same size
        min_duration = min(duration_list)
        '''


        # create list to store names of final videos
        video_names = []
        # trim all videos to length of shortest video, and give it a new name
        for video in front_trimmed_videos:
            fully_trimmed_video = video[1].subclip(0,min_duration)
            if video[0].split("_")[0] == "raw":
                video_name = "synced_" + video[0][4:]
            else:
                video_name = "synced_" + video[0]
            video_names.append(video_name) #add new name to list to reference for plotting
            fully_trimmed_video.write_videofile(video_name, preset = "faster")

        # reset our working directory
        os.chdir(base_path)


        return video_names # return names of new videos to reference for plotting



    def plot_waveforms(self, video_files, trimmed_video_paths, base_path):
        '''Take the original videos and the trimmed videos, and plot the audio to show if the cross correlation process was succesful.'''

        # get path to folder of audio files
        audio_path = os.path.join(base_path,"AudioFiles")

        # make the plot stand out!
        plt.style.use('seaborn')

        # create a plot for each audio signal, plus one to show final cross correlation
        number_of_plots = len(video_files) + 1
        # create plot structure
        fig, axs = plt.subplots(number_of_plots)

        # create color dictionary to plot all waveforms with the same color:
        color_dict = {}
        # add all of our original audio waveforms as separate plots to see them before analysis
        count = 0
        for file in video_files:
            # create a color that will change with each audio signal
            color = 'C' + str(count) #C0, C1, etc. are colors associated with the mpl stylesheet
            axs[count].plot(file[3], color)
            axs[count].set_title(file[2])
            # add filename, color combo to color dictionary
            color_dict[file[2]] = color
            print("plotting ", file[2], "with color", color)
            count += 1

        axs[number_of_plots-1].set_title("Synched Audio")
        for filepath in trimmed_video_paths:
            # create name for audio file
            audio_name = filepath.split(".")[0] + '.wav'
            # open video files
            video_file = mp.VideoFileClip(os.path.join(base_path,filepath), audio=True)
            
            # create .wav file of clip audio
            video_file.audio.write_audiofile(os.path.join(audio_path,audio_name))

            # extract raw audio from Wav file
            audio_signal, audio_rate = librosa.load(audio_name, sr = None)

            # remove "synced_" from audio name to be able to check it against color dictionary
            cam_name = audio_name.split("_")[1]
            # set color equal to corresponding color from dictionary
            color = color_dict[cam_name]
            print(cam_name,color)
            # plot audio 
            axs[number_of_plots-1].plot(audio_signal, color, linewidth = count)
            # line width is set to count so each drawn line is slightly smaller
            print("plotting ", audio_name, "with color", color)
            count -= 1

        # add spacing to the plot to prevent titles overlapping axes
        plt.tight_layout()
        # display the plot
        plt.show()

def main(session):
    '''Run the functions from the VideoSynchTrimming class to sync all videos with the given file type in the base path folder.
    Takes 2 command line arguments, session ID and folder path, with .'''

    # start timer to measure performance
    start_timer = time.time()

    # get arguments from command line
    args = sys.argv[1:]

    #parse arguments from command line, with excepts covering hardcoded default values - maybe get rid of these try/except for final script
    try:
        sessionID = args[0]
    except: 
        sessionID = "sync_test"
    try:
        fmc_data_path = args[1]
    except: 
        fmc_data_path = "/Users/Philip/Documents/Humon Research Lab/fmc_COM/"
    
    

    base_path = session.sessionID
    
    # instantiate class
    synch_and_trim = VideoSynchTrimming()
    synch_and_trim # this may be unnecessary?

    # set the base path and file type
    file_type = "MP4"  # should work with or without a period at the front, and in either case
    
    # create list of video clip in base path folder
    clip_list = synch_and_trim.get_clip_list(base_path, file_type)

    # get the files and store in list
    files, sr = synch_and_trim.get_files(base_path, clip_list)

    # find the frames per second of each video
    fps = synch_and_trim.get_fps_list(files)
    
    # check that our frame rates and audio sample rates are all equal
    synch_and_trim.check_rates(fps)
    synch_and_trim.check_rates(sr)
    
    # find the lags
    lag_list = synch_and_trim.find_lags(files, synch_and_trim.check_rates(sr))
    
    # use lags to trim the videos
    trimmed_videos = synch_and_trim.trim_videos(files, lag_list, base_path)

    # plot our results in order to verify everything worked
    # synch_and_trim.plot_waveforms(files, trimmed_videos, base_path)

    # end performance timer
    end_timer = time.time()
    
    #calculate and display elapsed processing time
    elapsed_time = end_timer - start_timer
    print("elapsed processing time in seconds:", elapsed_time)


if __name__ == "__main__":
    main()