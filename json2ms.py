import os, sys, time 
import logging
import argparse
import json
import redis
import threading
import glob
import subprocess
import time
from multiprocessing import Pool, Value



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')

#-- redis-py, see https://github.com/andymccurdy/redis-py
HOST_RDS = '10.0.0.3'
PORT_RDS = '6379'
rds = redis.StrictRedis(host=HOST_RDS, port=6379)

expire_sec_mpv = Value('i', 0)


###
## simulates the linux command, e.g. tail -F [file]
## see http://man7.org/linux/man-pages/man1/tail.1.html
###
def tail_file(fname, cbf, seconds_sleep=1):
    cur_f = open(fname, 'r')
    cur_ino = os.fstat(cur_f.fileno()).st_ino
    cur_f.seek(0, os.SEEK_END)
    
    try:
        while True:
            while True:
                lines = cur_f.readlines(5 * 1024 * 1024)
                cbf(lines)
                time.sleep(seconds_sleep)

                if not lines:
                    logging.info('EOF')
                    break

            try:
                #-- reopen the file if the old log file is rotated 
                if os.stat(fname).st_ino != cur_ino:
                    cur_f.close()
                    new_f = open(fname, 'r')
                    cur_f = new_f 
                    cur_ino = os.fstat(cur_f.fileno()).st_ino
                    logging.info('{0} inode changed, reopen the file'.format(fname))
            except IOError as e:
                logging.error(e)

    except KeyboardInterrupt as e:
        logging.error(e, exc_info=True)

    finally:
        if not cur_f.closed:
            cur_f.close()


def opp_parser(lines):
    for l in lines:
        j = json.loads(l)
        if 'code_name' not in j:
            continue
        if 'page_load' not in j:
            continue
            
        exit()


def tail_sync_file(rds, args):
    tail_file(args.src_fp, pool_sync)
    

###
## pipelining
## see https://github.com/andymccurdy/redis-py#pipelines,
##     https://redis.io/topics/pipelining,
##     https://redis.io/topics/mass-insert
##
def pipe_sync_file(rds, args) :
    jkey_c = args.c 
    jkey_t = args.t
    jkey_i = args.i
    jkey_v = args.v
    logging.info('combo key: ${0}.${1}.${2}'.format(jkey_c, jkey_t, jkey_i))
    logging.info('value key: {0}'.format(jkey_v))
    logging.info('ttl: {0}'.format(args.ttl))
    logging.info('command: {0}'.format(args.cmd_redis))
    logging.info('deamon mode: {0}'.format(args.deamon))

    state_files = FilesState(args.src_fpatt)
    new_state_files = state_files 
    while True:
        for fn in new_state_files.get_fnames():
            if new_state_files != state_files:
                s = state_files.get_state(fn)
                if s:
                    s_new = new_state_files.get_state(fn)
                    if s_new['ino'] == s['ino'] and s_new['md5'] == s['md5']:
                        logging.info('{n} has not change detected'.format(n=fn))
                        continue

            logging.info('{} counting ...'.format(fn))
            size_src = 0.0
            with open(fn, 'r') as f:
                for i, l in enumerate(f):
                    size_src = i
                    pass
            size_src += 1.0
            logging.info('{} has {:.0f} records'.format(fn, size_src))

            #-- disable the atomic nature of a pipeline
            #   see https://github.com/andymccurdy/redis-py#pipelines
            with rds.pipeline(transaction=False) as pipe:
                with open(fn, 'r') as f:
                    for i_line, l in enumerate(f):
                        j = json.loads(l)

                        if not jkey_c in j:
                            logging.error('{} is not found at line:{} in {}'.format(jkey_c, i_line, args.fn))
                            continue
                        if not jkey_t in j:
                            logging.error('{} is not found at line:{} in {}'.format(jkey_t, i_line, args.fn))
                            continue
                        if not jkey_i in j:
                            logging.error('{} is not found at line:{} in {}'.format(jkey_i, i_line, args.fn))
                            continue
                        if not jkey_v in j:
                            logging.error('{} is not found at line:{} in {}'.format(jkey_v, i_line, args.fn))
                            continue

                        k = '{c}_{ic}.{t}.{f}.{i}'.format(c=j[jkey_c], ic=args.index_cat, t=j[jkey_t], f=jkey_i, i=j[jkey_i])
                        v = j[jkey_v]

                        if RedisCommand.append == args.cmd_redis:
                            pipe.append(k, '{_v},'.format(_v=v))
                        elif RedisCommand.set == args.cmd_redis:
                            pipe.set(k, v)
                        elif RedisCommand.get == args.cmd_redis:
                            pipe.get(k)
                        elif RedisCommand.rpush == args.cmd_redis:
                            pipe.rpush(k, v)
                        elif RedisCommand.lpush == args.cmd_redis:
                            pipe.lpush(k, v)

                        if args.ttl:
                            pipe.expire(k, args.ttl)

                        size = i_line + 1
                        if 1 == size or size % 60000 == 0 or size_src <= size:
                            pipe.execute()
                            logging.info('{:.0f} {:.0f}%'.format(size, size / size_src * 100))

        if not args.deamon:
            break
        
        time.sleep(30)
        new_state_files = FilesState(args.src_fpatt)


class FilesState:
    def __init__(self, fpattern):
        self.fnames = glob.glob(fpattern)
        self.fname2state = {}

        for fn in self.fnames:
            logging.info('{n} is collecting state ...'.format(n=fn))
            self.fname2state[fn] = {}
            self.fname2state[fn]['ino'] = os.stat(fn).st_ino
            self.fname2state[fn]['mtime'] = os.stat(fn).st_mtime
            self.fname2state[fn]['md5'] = subprocess.check_output(['md5sum', fn]).strip().split()[0]

    def get_fnames(self):
        return self.fnames
    
    def get_state(self, fname):
        return self.fname2state.get(fname) 

from enum import Enum
class IndexCategory(Enum):
    gocc = 'gocc'
    mod = 'mod'
    opp = 'opp'
    oua = 'oua'

    def __str__(self):
        return self.value

class RedisCommand(Enum):
    append = 'append'
    get = 'get'
    set = 'set'
    rpush = 'rpush'
    lpush = 'lpush'

    def __str__(self):
        return self.value

if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_fpatt", help="source file path")

    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_i = 'id'
    jkey_v = 'indicators_raw'
    parser.add_argument('index_cat', type=IndexCategory, choices=list(IndexCategory), help="index category")
    parser.add_argument('cmd_redis', type=RedisCommand, choices=list(RedisCommand), help="redis commands")
    parser.add_argument("-c", default="{0}".format(jkey_c), help="source json key for code name, default: {0}".format(jkey_c))
    parser.add_argument("-t", default="{0}".format(jkey_t), help="source json key for table/mode name, default: {0}".format(jkey_t))
    parser.add_argument("-i", default="{0}".format(jkey_i), help="source json key for key/gid/item id, default: {0}".format(jkey_i))
    parser.add_argument("-v", default="{0}".format(jkey_v), help="source json key for value/rule content, default: {0}".format(jkey_v))
    parser.add_argument("-ttl", "--ttl", type=int, default=259200, help='live time of keys')
    parser.add_argument("-d", "--deamon", action='store_true', help='start as deamon mode')

    subparsers = parser.add_subparsers(help='sub-command help')
    parser_pipe = subparsers.add_parser("pipe", help="sync all file with pipelining")
    parser_pipe.set_defaults(func = pipe_sync_file)

    parser_tail = subparsers.add_parser("tail", help="sync once file grows")
    parser_tail.set_defaults(func = tail_sync_file)
 
    args = parser.parse_args()

    if args.deamon:
        try:
            #-- fork a child process, return 0 in the child and the child process id in the parent.
            #   see https://docs.python.org/2/library/os.html#os.fork
            pid = os.fork()

            #-- kill the current process if now is parent
            if 0 != pid:
                sys.exit(0)
        except OSError as e:
            logging.error(e, exc_info=True)
    
    args.func(rds, args)

 
