import argparse
import configparser
import pyaudio
from datetime import datetime
from pkg_resources import Requirement, resource_filename

import moody.audio as moody
from moody.communication import Publisher
from moody import communication, utility
from moody.utility.plotting import ThreadedPlotter


'''

Informations about the Residence/Area/Id of the audio sensor
These settings are static because of the test environment: specifically talking, the id should be
dynamically generated by the sensor local network through technologies such as bluetooth or zigbee. This
concept is not part of the thesis work.

'''

RESIDENCE = 0
AREA = 0
SENSOR_ID = 0
DATA_TYPE = "audio"


if __name__ == "__main__" :

    config = configparser.ConfigParser()

    try :

        if len ( config.read ( "/home/pi/Tesi/Moody_nomist/Moody/moody/moody.conf" ) ) == 0 :
            config.read ( resource_filename ( Requirement.parse ( "/home/pi/Tesi/Moody_nomist/Moody" ), "/home/pi/Tesi/Moody_nomist/Moody/moody/moody.conf" ) )

    except :

        raise ( "An error occurred while importing the default configuration!" )

    parser = argparse.ArgumentParser()
    parser.add_argument ( "--format", "-f", help = "Sample format, can only be int8, int16, int32", type = str, default = config["Sampling"]["FORMAT"] )
    parser.add_argument ( "--chunksize", "-s", help = "The dimension of a single audio chunk, the number of samples in a frame", type = int, default = int ( config["Sampling"]["CHUNK_SIZE"] ) )
    parser.add_argument ( "--samplerate", "-r", help = "The sample rate, defaults to 44100 Hz", type = int, default = int ( config["Sampling"]["SAMPLE_RATE"] ) )
    parser.add_argument ( "--windowsize", "-w", help = "The size of the audio analysis window, where every element is a frame", type = int, default = int ( config["Analysis"]["WINDOW_SIZE"] ) )
    parser.add_argument ( "--silencerate", "-sr", help = "The minimum amount of zero energy frames in a window for it to be considered silence", type = float, default = float ( config["Analysis"]["SILENCE_RATE"] ) )
    parser.add_argument ( "--musicthresh", "-mt", help = "The value under which the difference between peaks is small enough to be considered music", type = float, default = float ( config["Analysis"]["MUSIC_THRESHOLD"] ) )
    parser.add_argument ( "--verbose", "-v", help = "If the verbose option is selected, the program prints informations about the energy level of every analyzed frame", action = "store_true" )
    parser.add_argument ( "--offline", "-o", help = "If the offline option is selected, the data will be analyzed locally and not sent to the MQTT broker", action = "store_true" )
    parser.add_argument ( "--silencethresh", "-st", help = "If the selencethresh option is selected, the program will set a silence threshold according to the environment noise that it captures while initializing", action = "store_true" )
    parser.add_argument ( "--plotting", "-p", help = "If the plotting option is selected, a subthread will generate plots of the captured audio every 15 seconds", action = "store_true" )

    args = parser.parse_args()


    FORMAT = None
    CHUNK_SIZE = args.chunksize
    SAMPLE_RATE = args.samplerate
    WINDOW_SIZE = args.windowsize
    SILENCE_RATE = args.silencerate
    MUSIC_THRESHOLD = args.musicthresh
    VERBOSE = args.verbose
    OFFLINE = args.offline
    THRESHOLD_TO_READ = args.silencethresh
    PLOTTING = args.plotting
    BROKER_ADDRESS = config["Communication"]["BROKER_ADDRESS"]
    BROKER_PORT = int ( config["Communication"]["BROKER_PORT"] )


    if args.format == "int32" :

        FORMAT = pyaudio.paInt32

    elif args.format == "int16" :

        FORMAT = pyaudio.paInt16

    elif args.format == "int8" :

        FORMAT = pyaudio.paInt8

    else :

        raise Exception ( "Invalid format!" )

    if PLOTTING:
        plotter = ThreadedPlotter( FORMAT )

    if VERBOSE :

        moody.logger.console( True )
        communication.logger.console( True )
        utility.plotting.logger.console( True )
    '''

    Initializing the audio stream and MQTT client

    '''
    running = True
    moody = moody.MoodyAudio ( audio_format = FORMAT, chunk_size = CHUNK_SIZE, sample_rate = SAMPLE_RATE, window_size = WINDOW_SIZE )

    '''

    Checking for the silence threshold

    '''

    print ( "Recording audio to check the silence frames energy level, don't speak..." )
    if THRESHOLD_TO_READ:
        moody.set_silence_threshold()

    '''

    Initialize the publisher client and attempts to connect to the broker

    '''

    if not OFFLINE :

        publisher = None

        try :

            sensor_id = "Sensor_{}_{}_{}".format( RESIDENCE, AREA, SENSOR_ID )
            publisher = Publisher( sensor_id )
            publisher.connect( BROKER_ADDRESS, port = BROKER_PORT )
            publisher.loop_start()
            sensor_topic = "{}_{}/{}/{}".format( RESIDENCE, AREA, DATA_TYPE, SENSOR_ID )

        except:
            running  = False

    '''

    Start the plotter thread

    '''

    if PLOTTING:
        plotter.start()

    '''

    The program is now connected to the broker via the publisher Client and has initialized an input
    audio stream. It can begin the sampling and analysis of the data.

    '''



    with open( "/home/pi/Tesi/Moody_nomist/stats.log", mode="w+" ) as stats_dump:

        while running :

            try :
                start = datetime.now()
                stats_dump.write("{} inizio acquisizione chunk\n".format( start ) )
                print("{} inizio acquisizione chunk".format( start ) )
                data_window = moody.listen( single = True )
                finish = datetime.now()
                stats_dump.write("{} fine acquisizione chunk\n".format( finish ) )
                stats_dump.write("t_acquisizione = {}\n".format( finish - start ) )
                print("{} fine acquisizione chunk".format( finish ) )
                print("t_acquisizione = {}".format( finish - start ) )

                if not OFFLINE :
                    start = datetime.now()
                    stats_dump.write("{} inizio invio chunk\n".format( start ) )
                    print("{} inizio invio chunk".format( start ) )
                    publisher.publish ( topic = sensor_topic, payload = data_window, qos = 0 )
                    finish = datetime.now()
                    stats_dump.write("{} fine invio chunk\n".format( finish ) )
                    stats_dump.write("t_invio = {}\n".format( finish - start ) )
                    print("{} fine invio chunk".format( finish ) )
                    print("t_invio = {}".format( finish - start ) )


                #plotter.append ( data_window, frame_type )

            except ( KeyboardInterrupt, ConnectionError ) as e :

                if not OFFLINE :
                    if isinstance( e, ConnectionError ):
                        publisher.reconnect()
                        continue
                    publisher.disconnect()

                moody.close()
                #plotter.close()
                running = False



    print ( "\nBye!" )
