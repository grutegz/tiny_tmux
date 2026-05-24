import argparse
from mux import Multiplexer

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Minimalistic terminal multiplexor for unix systems.'
    )

    parser.add_argument(
        'cmd',
        nargs = '?',
        help = 'Command, that will be executed in first session.'
    )    
    
    args = parser.parse_args()
    
    command = args.cmd if args.cmd else '/bin/bash'
    mux = Multiplexer(command)
    mux.run()