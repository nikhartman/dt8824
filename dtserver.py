''' a tornado server to handle data acquisition from the DT8824 

    things to implement:

    setup_all -- frequency, gain, channels
    get/set commands

    start/stop
    fetch
    stream_next
    stream_stop

    question: do I want an HTTP server or TCP server?

'''

import json
import dt8824

from tornado.tcpserver import TCPServer
from tornado import gen
from tornado.ioloop import IOLoop

class DTServer(TCPServer):

    def __init__(self, **kwargs)
        TCPServer.__init__(**kwargs)
        self.inst = dt8824.DT8824()

    @gen.coroutine
    def handle_stream(self, stream, address):
        # I have no idea what this needs to do



if __name__ == '__main__':
    server = DTServer() # start server
    sever.listen(8824) # define port/start listening
    io_loop = IOLoop.current() # create IO loop to handle incoming connections
    io_loop.start() # start IO loop
