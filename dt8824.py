# a driver to provide basic funcitonality for the DT8824
# probably will work on Ubuntu/Raspian
# probably on other *nix systems  with some changes
# hopeless on Windows

import os, re, time
import vxi11

gain_ref = {1:(-10.0,10.0), 8:(-1.25,1.25), 16:(-0.625,0.625), 32:(-0.3125,0.3125)}

def bytes_to_int(b):
    return ((b[0]<<24) + (b[1]<<16) + (b[2]<<8) + b[3])

def get_ip_address(interface):
    ''' find the IP address of the DT8824 connected to interface '''
    try: 
        out = os.popen('ip addr show {0}'.format(interface)).read()
    except:
        raise ValueError('Could not get ifconfig for {0}'.format(interface))

    ip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', out )
    if len(ip)<2:
        raise ValueError('No broadcast IP found for {0}'.format(interface))

    try:
        out = os.popen('ping -c 3 -b {0}'.format(ip[1])).read()
    except:
        raise ValueError('Could not successfully ping broadcast IP on {0}'.format(interface))

    dtip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', out )
    dtip = [i for i in dtip if i not in ip]
    if len(ip)==0:
        raise ValueError('No instrument IP found during broadcast IP ping')
    else:
        return dtip[0]

class DT8824():
    ''' class for controlling the Data Translation 8824 ADC '''

    def __init__( self, interface='eth0'):
        # interface is the network interface that the DT8824 is connected to 
        
        self.ip = get_ip_address(interface) # get IP
        self.vx_handle = vxi11.Instrument(self.ip) # open instrument

        # check IDN string
        self.idn = self.vx_handle.ask('*IDN?').split(',')                      
        if self.idn[0]=='Data Translation' and self.idn[1]=='DT8824':
            pass
        else:
            raise ValueError('Incorrect IDN string: '.format(out))    

        # enable password protected commands
        response = self.ask(':SYST:PASS:CEN:STAT?')
        if(int(response) == 0): # commands already enabled if response == 1
            # try to enable it
            self.write(':SYST:PASS:CEN admin')
            time.sleep(0.1) # wait 100ms
            response = self.ask(':SYST:PASS:CEN:STAT?')
            if(int(response) == 0):  # commands now enabled
                raise ValueError('Could not enable password protected commands.')
        
        # set variables
        self.running = False
        self.istream = 0
        self.nstream = 0

        # setup
        self.get_frequency(); # check frequency settings
        self.get_channels(); # check channel settings
        self.get_gain();
        self.get_buffer_type();
 
    def close(self):
        self.vx_handle.close()

    ### basic I/O ###

    def write(self, message, **kwargs):
        ''' write command to instrument '''
        self.vx_handle.write(message, **kwargs)

    def read(self, **kwargs):
        ''' read string from instrument '''
        return self.vx_handle.read(**kwargs)

    def ask(self, message, **kwargs):
        ''' write message, read response string '''
        return self.vx_handle.ask(message, **kwargs)
 
    def read_raw(self, **kwargs):
        ''' read raw binary data '''
        return self.vx_handle.read_raw(**kwargs)

    def ask_raw(self, message, **kwargs):
        ''' write message, read binary response string '''
        self.vx_handle.write(message)
        return self.vx_handle.read_raw(**kwargs)

    ### status ###

    def get_status(self):
        status_str = '{0:08b}'.format(int(self.ask('AD:STAT?')))
        return [int(s) for s in status_str]

    ### setup channel parameters ###
    
    def setup_all(self, frequency, gains, channels, buffer_type = 'wrap'):
        ''' set all parameters for DT8824 '''
        self.set_frequency(frequency)
        self.set_gain(gains)
        self.set_channels(channels)
        self.set_buffer_type(buffer_type)

    def get_frequency(self):
        self.frequency = float(self.ask(':AD:CLOC:FREQ?'))
        return self.frequency

    def set_frequency(self, frequency):
        if frequency < 1.175:
            frequency = 1.175
            print('Frequency set to MIN (1.175Hz)')
        elif frequency > 4800.0:
            frequency = 4800.0
            print('Frequency set to MAX (4800.0Hz)')
        
        self.write(':AD:CLOC:FREQ {0:.3f}'.format(frequency))
        self.frequency = float(self.ask(':AD:CLOC:FREQ?')) # values are rounded to 4800/n (sort of)

    def get_channels(self):
        ''' get a comma separated list of which channels are enabled (0-3) '''
        chn = self.ask(':AD:ENAB?').split(',')
        self.channels = [int(i) for i in chn]
        return self.channels

    def set_channels(self, channels):
        ''' set channels on(off) with 1(0) list '''
        self.write(':AD:ENAB OFF, (@1:4)') # turn all channels off
        channel_str = ','.join([str(i+1) for i,c in enumerate(channels) if c==1])
        self.write(':AD:ENAB ON, (@{0})'.format(channel_str))
        self.channels = channels
    
    def get_gain(self):
        ''' returns the gain settings for each channel '''
        gn = self.ask(':AD:GAIN?').split(',') 
        self.gain = [int(g) for g in gn]
        self.limits = [gain_ref[g] for g in self.gain]
        return self.gain

    def set_gain(self, gains):
        ''' set gains for all channels.
            assumes gains is a list of valid gain values '''
        gains = [min(gain_ref.keys(), key=lambda x:abs(x-g)) for g in gains]
        for i,g in enumerate(gains):
            self.write(':AD:GAIN {0:d}, (@{1:d})'.format(g, i+1))
        self.gain = gains
        self.limits = [gain_ref[g] for g in self.gain]

    def get_buffer_type(self):
        response = self.ask(':AD:BUFF:MODE?');
        if response=='WRAp':
            self.buff = 'wrap'
        elif response=='NOWRAp':
            self.buff = 'nowrap'
        return self.buff

    def set_buffer_type(self, buffer_type):
        ''' set the buffer to wrap or nowrap '''
        if buffer_type.lower()=='wrap':
            self.write(':AD:BUFF:MODE WRA')
            self.buff = 'wrap'
        elif buffer_type.lower()=='nowrap':
            self.write(':AD:BUFF:MODE NOWRA')
            self.buff = 'nowrap'

    ### data acquisition ###

    def start_acquisition(self):
        ''' start reading into bufer '''
        self.write(':AD:TRIG:SOURR IMM')
        self.write(':AD:ARM')
        self.write(':AD:INIT')
        self.running = True
                
    def stop_acquisition(self):
        ''' stop reading '''
        self.write(':AD:ABOR')
        self.running = False

    def fetch(self, fetch_type = 'array', n=None):
        ''' get the most recent n readings with the current setup '''
        
        if not self.running:
            self.start_acquisition()
        
        if not n:
            nrequest = 1
        else:
            nrequest = n

        data = []
        ntotal = 0
        i = 0
        while(ntotal<nrequest): 
            if i==0:
                # find the newest data point and start reading there
                _, startidx = (int(j) for j in self.ask(':AD:STAT:SCA?').split(','))
            out = list(self.ask_raw(':AD:FETCH? {0:d}'.format(startidx+ntotal+1))[:-1])
            nread = bytes_to_int(out[8:12])
            if nread!=0:    
                # parse data
                data.extend([bytes_to_int(out[k:k+4]) for k in range(28, len(out), 4)])
            ntotal += nread
            i+=1

        if fetch_type=='array':
            if not n:
                return data
            else:
                return data[:n]
        elif fetch_type=='single':
            if not n:
                return sum(data)/len(data)
            else:
                return sum(data[:n])/n

    def stream_next(self):

        if not self.running:
            self.start_acquisition()

        while(True):
            if self.istream==0:
                # find the newest data point and start reading there
                _, self.start_stream = (int(j) for j in self.ask(':AD:STAT:SCA?').split(','))
            out = list(self.ask_raw(':AD:FETCH? {0:d}'.format(self.start_stream+self.nstream+1))[:-1])
            nread = bytes_to_int(out[8:12])
            self.istream+=1
            if nread!=0:
                self.nstream+=nread    
                break

        return [bytes_to_int(out[k:k+4]) for k in range(28, len(out), 4)]
    
    def stream_stop(self):
        self.istream = 0
        self.nstream = 0
        self.stop_acquisition()        

