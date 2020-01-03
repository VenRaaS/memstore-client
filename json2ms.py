#!/usr/bin/python
import os, sys, time 
import logging
import logging.config
from logging.handlers import RotatingFileHandler
import argparse
import json
import redis
import threading
import glob
import subprocess
import time
import re
from multiprocessing import Pool, Value
from distutils.version import StrictVersion


#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %I:%M:%S')

#-- redis-py, see https://github.com/andymccurdy/redis-py
HOST_RDS = os.getenv('HOST_RDS', "ms-node-01")
PORT_RDS = '6379'
TIMEOUT_IN_SEC = 1
rds = redis.StrictRedis(host=HOST_RDS, port=6379, socket_connect_timeout=TIMEOUT_IN_SEC)

SLEEP_FOR_FILE_CHANGE_DETECTION_IN_SEC = 300

expire_sec_mpv = Value('i', 0)

IS_REDIS_LE_VER3 = StrictVersion('3.0') <= StrictVersion(redis.__version__)
IS_PYTHON_LE_VER27 = StrictVersion('2.7') <= StrictVersion(sys.version.split()[0])



##
## pipelining
## see https://github.com/andymccurdy/redis-py#pipelines,
##     https://redis.io/topics/pipelining,
##     https://redis.io/topics/mass-insert
##
def rds_pipe_worker(tuple_list):
    resp_list = []

    wait_sec = 0
    retry_sec = 300
    while wait_sec < retry_sec:
        try:
            #-- disable the atomic nature of a pipeline
            #   see https://github.com/andymccurdy/redis-py#pipelines
            with rds.pipeline(transaction=False) as pipe:
                for args, rdscmds in tuple_list:
                    for cmd in rdscmds:
                        if RedisCommand.append == cmd[0]:
                            k, v = cmd[1:] 
                            pipe.append(k, '{_v},'.format(_v=v))
                        elif RedisCommand.set == cmd[0]:
                            k, v = cmd[1:] 
                            pipe.set(k, v)
                        elif RedisCommand.get == cmd[0]:
                            k = cmd[1] 
                            pipe.get(k)
                        elif RedisCommand.rpush == cmd[0]:
                            k, v = cmd[1:] 
                            pipe.rpush(k, v)
                        elif RedisCommand.lpush == cmd[0]:
                            k, v = cmd[1:] 
                            pipe.lpush(k, v)
                        elif RedisCommand.lrange == cmd[0]:
                            k, start, stop = cmd[1:]
                            pipe.lrange(k, start, stop)
                        elif RedisCommand.ltrim == cmd[0]:
                            k, start, stop = cmd[1:]
                            pipe.ltrim(k, start, stop)
                        elif RedisCommand.expire == cmd[0]:
                            k, v = cmd[1:] 
                            pipe.expire(k, v)
                        elif RedisCommand.zadd == cmd[0]:
                            k, s, v = cmd[1:]
                            #-- input parameters have changed since 3.0
                            #   see https://github.com/andymccurdy/redis-py/blob/master/CHANGES#L100
                            if IS_REDIS_LE_VER3:
                                pipe.zadd(k, {v:s})
                            else:
                                pipe.zadd(k, s, v)
                        elif RedisCommand.zremrangebyscore == cmd[0]:
                            k, minscore, maxscore = cmd[1:]
                            pipe.zremrangebyscore(k, minscore, maxscore)
                        elif RedisCommand.zremrangebyrank == cmd[0]:
                            k, start, stop = cmd[1:]
                            pipe.zremrangebyrank(k, start, stop)

                resp_list = pipe.execute()
                if IS_PYTHON_LE_VER27:
                    logger.info('pipelining {num:,} rows'.format(num=len(tuple_list)))
                else:
                    logger.info('pipelining {num} rows'.format(num=len(tuple_list)))
                retry_sec = 0

        except redis.ResponseError as e:
            if 'redis is busy running a script' in str(e).lower():
                logger.warn('redis is busy, wait a second to retry ...')
                time.sleep(10)
                wait_sec += 10
            elif 'oom command not allowed when used memory' in str(e).lower():
                logger.error(e)
                sys.exit()

        except KeyboardInterrupt as e:
            logger.error(e, exc_info=True)
            retry_sec = 0

    return resp_list

##
## simulates the linux command, e.g. tail -F [file]
## see http://man7.org/linux/man-pages/man1/tail.1.html
##
def tail_file(args, parser_cbf, seconds_sleep=3):
    fname = args.src_fp
    cur_f = open(fname, 'r')
    cur_ino = os.fstat(cur_f.fileno()).st_ino
    
    #-- move to start read position  
    if args.startfromend:
        cur_f.seek(0, os.SEEK_END)
    
    try:
        while True:
            while True:
                lines = cur_f.readlines(20 * 1024 * 1024)
#                print lines
                if 0 < len(lines):
                    parser_cbf(args, fname, 0, lines)

                if not lines:
                    logger.info('EOF')
                    time.sleep(seconds_sleep)
                    break

            try:
                #-- reopen the file if the old log file is rotated 
                if os.stat(fname).st_ino != cur_ino:
                    cur_f.close()
                    new_f = open(fname, 'r')
                    cur_f = new_f 
                    cur_ino = os.fstat(cur_f.fileno()).st_ino
                    logger.info('{0} inode changed, reopen the file'.format(fname))
            except IOError as e:
                logger.error(e)

    except KeyboardInterrupt as e:
        logger.error(e, exc_info=True)

    finally:
        if not cur_f.closed:
            cur_f.close()


def tail_sync_file(args):
    tail_file(args, weblog_parser)


def pipe_file(args, parser_cbf):
    state_files = FilesState(args.src_fp, args.deamon)
    new_state_files = state_files 
    while True:
        for fn in new_state_files.get_fnames():
            if new_state_files != state_files:
                s = state_files.get_state(fn)
                if s:
                    s_new = new_state_files.get_state(fn)
                    if s_new['ino'] == s['ino'] and s_new['md5'] == s['md5']:
                        logger.info('{n} has not change detected'.format(n=fn))
                        continue

            logger.info('{fn} counting ...'.format(fn=fn))
            linnum_src = 0.0
            with open(fn, 'r') as f:
                for i, l in enumerate(f, 1):
                    linnum_src = i
                    pass
            if IS_PYTHON_LE_VER27:
                logger.info('{fn} has {lnum:,.0f} records'.format(fn=fn, lnum=linnum_src))
            else:
                logger.info('{fn} has {lnum} records'.format(fn=fn, lnum=linnum_src))
            
            with open(fn, 'r') as f:
                linenum = 0.0
                while True:
                    lines = f.readlines(10 * 1024 * 1024)
                    if 0 < len(lines):
                        parser_cbf(args, fn, linenum, lines)
                    else:
                        break

                    linenum += len(lines)
                    if IS_PYTHON_LE_VER27:
                        logger.info('{lnum:,.0f} {pct:,.0f}%'.format(lnum=linenum, pct=linenum / linnum_src * 100))
                    else:
                        logger.info('{lnum} {pct}%'.format(lnum=linenum, pct=round(linenum / linnum_src * 100,1)))

        if not args.deamon:
            break
        
        time.sleep(SLEEP_FOR_FILE_CHANGE_DETECTION_IN_SEC)
        new_state_files = FilesState(args.src_fp, args.deamon)


def weblog_parser(args, fn, linebase, lines):
    tuple_list = []
    try:
        for linenum, l in enumerate(lines, 1):
            #-- get the columns 
            cols = l.split('\t')
            
            #-- log comes form venapis, e.g. {"pageload":["{\"action\":...}"], "code_name":["sohappy"], ...}
            if 1 == len(cols):
                js = json.loads(l)
            #-- log comes from td-agent, e.g. 2018-09-17T11:51:00+08:00    apid.data   $json_payload
            elif 3 == len(cols):
                js = json.loads(cols[-1])
                if 'logbody' not in js:
                    logger.error('invalid td-weblog due to lack of key "{k}"'.format(k='logbody'))
                    continue
                js = json.loads(js['logbody'])
            else:
                logger.error('invalid weblog due to unknown format')
                continue         

            #-- js, log content with venapis form
            if args.c not in js or not js[args.c]:
                logger.error('invalid weblog due to lack of key "{k}"'.format(k=args.c))
                continue
            if 'api_logtime' not in js or not js ['api_logtime']:
                logger.error('invalid weblog due to lack of key "{k}"'.format(k='api_logtime'))
                continue

            act = None
            cn = js[args.c][0]
            logdt = js['api_logtime'][0][:19]
            
            rdscmds = []
            #-- iter k, v, e.g. "code_name":[...], "agent":[...], "api_logtime":[...], ...
            for k, v in js.iteritems() if hasattr(js, 'iteritems') else js.items():
                #-- find action content payload, e.g. "pageload":["{...}"]
                if 0 < len(v) \
                     and (isinstance(v[0], str) or isinstance(v[0], unicode)) \
                     and k in v[0]:
                    act = k
                    js = json.loads(v[0])
                    ## in case, missing 'ven_guid' key in json, use cc_guid equal ven_guid
                    if not 'ven_guid' in js and js['cc_guid']:
                        js['ven_guid'] = js['cc_guid']
                    
                    #-- oua
                    if 'ven_guid' in js and 'uid' in js and js['ven_guid'] and js['uid']:
                        k = ['{c}_oua'.format(c=cn), 'guid2uid', js['ven_guid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'uid':js['uid']}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        if logdt:
                            score = float(re.sub('[- :T]', '', logdt)[:14])
                            rdscmds.append((RedisCommand.zadd, k, score, v))
                            rdscmds.append((RedisCommand.zremrangebyrank, k, 0, -6))
                            rdscmds.append((RedisCommand.expire, k, args.ttl))
                        else:
                            logger.error('{} is not found at line:{} in {}'.format('logdt', linenum+linebase, fn))

                        k = ['{c}_oua'.format(c=cn), 'uid2guids', js['uid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'ven_guid':js['ven_guid']}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        if logdt:
                            score = float(re.sub('[- :T]', '', logdt)[:14])
                            rdscmds.append((RedisCommand.zadd, k, score, v))
                            rdscmds.append((RedisCommand.zremrangebyrank, k, 0, -6))
                            rdscmds.append((RedisCommand.expire, k, args.ttl))
                        else:
                            logger.error('{} is not found at line:{} in {}'.format('logdt', linenum+linebase, fn))

                    #-- opp 
                    if 'pageload' == act and 'ven_guid' in js \
                        and 'gid' in js and 'categ_code' in js \
                        and js['gid'] and js['categ_code']:
                        k = ['{c}_opp'.format(c=cn), act, js['ven_guid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'gid':js['gid'], 'category_code':js['categ_code'], 'insert_dt':logdt}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')

                        rdscmds.append((RedisCommand.lpush, k, v))
                        rdscmds.append((RedisCommand.ltrim, k, 0, 60))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))

                    #-- user_prefer_goods
                    if 'user_prefer_goods' == act  and 'uid' in js \
                        and 'gid' in js  \
                        and js['gid'] and js['uid']:
                        k = ['{c}_opp'.format(c=cn), act, js['uid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'gid':js['gid'], 'w_list_type':js['w_list_type'], 'insert_dt':logdt}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')

                        rdscmds.append((RedisCommand.lpush, k, v))
                        rdscmds.append((RedisCommand.ltrim, k, 0, 60))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))

                    #-- cartadd 
                    #if 'cartadd' == act and 'ven_guid' in js \
                    #    and 'gid' in js and 'categ_code' in js \
                    #    and js['gid'] and js['categ_code']:
                    #    k = ['{c}_opp'.format(c=cn), act, js['ven_guid']]
                    #    k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                    #    v_obj = {'gid':js['gid'], 'category_code':js['categ_code'], 'insert_dt':logdt}
                    #    v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')

                    #    rdscmds.append((RedisCommand.lpush, k, v))
                    #    rdscmds.append((RedisCommand.ltrim, k, 0, 60))
                    #    rdscmds.append((RedisCommand.expire, k, args.ttl))

                    #-- checkout
                    if 'checkout' == act \
                        and 'trans_i' in js and js['trans_i'] \
                        and 'ven_guid' in js and 'uid' in js and js['ven_guid'] and js['uid']:
                        k = ['{c}_opp'.format(c=cn), act, js['ven_guid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'trans_i':js['trans_i'], 'insert_dt':logdt}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')

                        rdscmds.append((RedisCommand.lpush, k, v))
                        rdscmds.append((RedisCommand.ltrim, k, 0, 10))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))

                    #-- unfavadd
                    if 'unfavadd' == act \
                        and 'ven_guid' in js and 'gid' in js \
                        and js['ven_guid'] and js['gid']:
                        k = ['{c}_opp'.format(c=cn), act, js['ven_guid']]
                        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')
                        v_obj = {'gid':js['gid'], 'insert_dt':logdt}
                        v = json.dumps(v_obj, separators=(',', ':'), ensure_ascii=False).encode('utf8')

                        rdscmds.append((RedisCommand.lpush, k, v))
                        rdscmds.append((RedisCommand.ltrim, k, 0, 20))
                        rdscmds.append((RedisCommand.expire, k, args.ttl))

                    if 0 < len(rdscmds):
                        tuple_list.append( (args, rdscmds) )

        rds_pipe_worker(tuple_list)
    except Exception as e:
        logger.error(e, exc_info=True)


def goccmod_parser(args, fn, linebase, lines):
    jkey_c = args.c 
    jkey_t = args.t
    jkey_k = args.k
    jkeys_vals = args.valkeys

    #-- extract date from filename, i.e. %Y%m%d
    date = None
    m = re.search(r'[12]\d{3}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', fn)
    if m:
        date = m.group(0)
    else:
        logger.error('DATE pattern (%Y%m%d) is not found from filename: {fn}'.format(fn=fn))
        return
                    
    tuple_list = []
    for linenum, l in enumerate(lines, 1):
        try:
            j = json.loads(l)

            if not jkey_c in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_c, linenum+linebase, fn))
                continue
            if not jkey_t in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_t, linenum+linebase, fn))
                continue
            if not jkey_k in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_k, linenum+linebase, fn))
                continue

            if jkeys_vals:
                for valkey in jkeys_vals:
                    if not valkey in j:
                        logger.error('{k}, {vk} is not found at line:{ln} in {fn}'.format(k=j[jkey_k], vk=valkey, ln=linenum+linebase, fn=fn))
                        continue

            idkey = jkey_k.lower() if args.lowercase_key else jkey_k
            k = ['{c}_{ic}_{d}'.format(c=j[jkey_c], ic=args.index_cat, d=date), j[jkey_t], j[jkey_k]]
            k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')

            v_obj = {}
            if jkeys_vals:
                for vk in jkeys_vals:
                    if vk not in j:
                        logger.error('key:{vkey} does not in json'.format(vkey=vk))
                        continue

                    if args.lowercase_key:
                        v_obj[vk.lower()] = j[vk]
                    else:
                        v_obj[vk] = j[vk]
            else:
                v_obj = j
            v = json.dumps(v_obj, ensure_ascii=False).encode('utf8')

            rdscmds = []
            #-- push data to list
            if not args.datetimekey:
                rdscmds.append((RedisCommand.lpush, k, v))
                rdscmds.append((RedisCommand.ltrim, k, 0, 0))
                rdscmds.append((RedisCommand.expire, k, args.ttl))
            #-- add data to sorted set
            else:
                if args.datetimekey not in j:
                    logger.error('args.datetimekey is not found at line:{} in {}'.format(linenum+linebase, fn))
                    continue

                # extract YYYYMMDD as score
                dt = j[args.datetimekey]
                score = float(re.sub('[- ]', '', dt)[:8])
                score_yest = score - 1
                rdscmds.append((RedisCommand.zadd, k, score, v))
                rdscmds.append((RedisCommand.zremrangebyscore, k, '-inf', score_yest))
                rdscmds.append((RedisCommand.expire, k, args.ttl))

            tuple_list.append((args, rdscmds))
        except Exception as e:
            logger.error(e, exc_info=True)

    rds_pipe_worker(tuple_list)


def update_goods_parser(args, fn, linebase, lines):
    jkey_c = args.c 
    jkey_t = args.t
    jkey_k = args.k
    jkeys_vals = args.valkeys

    #-- extract date from filename, i.e. %Y%m%d
    date = None
    m = re.search(r'[12]\d{3}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', fn)
    if m:
        date = m.group(0)
    else:
        logger.error('DATE pattern (%Y%m%d) is not found from filename: {fn}'.format(fn=fn))
        return
                  
    #-- get keys from update json file   
    tuple_list = []
    for linenum, l in enumerate(lines, 1):
        try:
            j = json.loads(l)

            if not jkey_c in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_c, linenum+linebase, fn))
                continue
            if not jkey_t in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_t, linenum+linebase, fn))
                continue
            if not jkey_k in j:
                logger.error('{} is not found at line:{} in {}'.format(jkey_k, linenum+linebase, fn))
                continue

            if jkeys_vals:
                for valkey in jkeys_vals:
                    if not valkey in j:
                        logger.error('{k}, {vk} is not found at line:{ln} in {fn}'.format(k=j[jkey_k], vk=valkey, ln=linenum+linebase, fn=fn))
                        continue

            idkey = jkey_k.lower() if args.lowercase_key else jkey_k
            k = ['{c}_{ic}_{d}'.format(c=j[jkey_c], ic='gocc', d=date), j[jkey_t], j[jkey_k]]
            k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')

            rdscmds = []
            rdscmds.append((RedisCommand.lrange, k, 0, 0))

            tuple_list.append((args, rdscmds))
        except Exception as e:
            logger.error(e, exc_info=True)

    #-- get goods info list from ms 
    msGoods_dic = {} 
    if 0 < len(tuple_list):
        msGoods = rds_pipe_worker(tuple_list)
        for l in msGoods:
            if len(l) <= 0:
                continue
            j = json.loads(l[0])
            if 'gid' in j:
                msGoods_dic[ j['gid'] ] = j
 
    #-- upsert goods into ms
    tuple_list = []
    for linenum, l in enumerate(lines, 1):
        update_j = json.loads(l)
        
        k = ['{c}_{ic}_{d}'.format(c=update_j[jkey_c], ic='gocc', d=date), update_j[jkey_t], update_j[jkey_k]]
        k = json.dumps(k, separators=(',', ':'), ensure_ascii=False).encode('utf8')

        v_obj = {}
        gid = update_j[jkey_k]
        if gid in msGoods_dic:
            ms_j = msGoods_dic[gid]
            v_obj = ms_j

        if jkeys_vals:
            isValid = True
            for vk in jkeys_vals:
                if vk not in update_j:
                    logger.error('{gid}, key [{vkey}] does not in update json'.format(gid=gid, vkey=vk))
                    isValid = False
                    break

                if args.lowercase_key:
                    v_obj[vk.lower()] = update_j[vk]
                else:
                    v_obj[vk] = update_j[vk]

            # abandon the record if any of value-keys is not found 
            if not isValid:
                continue
        else:
            for k, v in update_j.iteritems() if hasattr(update_j, 'iteritems') else update_j.items():
                if args.lowercase_key:
                    v_obj[k.lower()] = v
                else:
                    v_obj[k] = v

        v = json.dumps(v_obj, ensure_ascii=False).encode('utf8')

        rdscmds = []
        rdscmds.append((RedisCommand.lpush, k, v))
        rdscmds.append((RedisCommand.ltrim, k, 0, 0))
        rdscmds.append((RedisCommand.expire, k, args.ttl))

        tuple_list.append((args, rdscmds))
        
    rds_pipe_worker(tuple_list)


def pipe_sync_file(args):
    if IndexCategory.gocc == args.index_cat or \
        IndexCategory.mod == args.index_cat:
        jkey_c = args.c 
        jkey_t = args.t
        jkey_k = args.k
        jkeys_vals = args.valkeys
        logger.info('combo key: ${0}.${1}.${2}'.format(jkey_c, jkey_t, jkey_k))
        logger.info('value key: {0}'.format(jkeys_vals))
        logger.info('ttl: {0}'.format(args.ttl))
        logger.info('deamon mode: {0}'.format(args.deamon))
        pipe_file(args, goccmod_parser)

    elif IndexCategory.weblog == args.index_cat:
        pipe_file(args, weblog_parser)

    elif IndexCategory.update_goods == args.index_cat:
        pipe_file(args, update_goods_parser)


class FilesState:
    def __init__(self, fpattern, dohash=False):
        logger.info('find all pathnames matching pattern \"{p}\" ...'.format(p=fpattern))
        self.fnames = sorted(glob.glob(fpattern))
        self.fname2state = {}

        for fn in self.fnames:
            logger.info('collecting {n} state ...'.format(n=fn))
            self.fname2state[fn] = {}
            self.fname2state[fn]['ino'] = os.stat(fn).st_ino
            self.fname2state[fn]['mtime'] = os.stat(fn).st_mtime
            if dohash:
                self.fname2state[fn]['md5'] = subprocess.check_output(['md5sum', fn]).strip().split()[0]

    def get_fnames(self):
        return self.fnames
    
    def get_state(self, fname):
        return self.fname2state.get(fname) 


from enum import Enum
class IndexCategory(Enum):
    gocc = 'gocc'
    mod = 'mod'
    weblog = 'weblog'
    update_goods = 'update_goods'

    def __str__(self):
        return self.value

class RedisCommand(Enum):
    append = 'append'
    get = 'get'
    set = 'set'
    rpush = 'rpush'
    lpush = 'lpush'
    lrange = 'lrange'
    ltrim = 'ltrim'
    expire = 'expire'
    zadd = 'zadd'
    zremrangebyscore = 'zremrangebyscore'
    zremrangebyrank = 'zremrangebyrank'

    def __str__(self):
        return self.value


if '__main__' == __name__:

    pwd_dir = os.path.dirname(os.path.realpath(__file__))
    log_dir = os.path.join(pwd_dir, 'log')
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    logging.config.fileConfig(os.path.join(pwd_dir,'logging.conf'))
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser()
    parser.add_argument("src_fp", help="source file path")
    parser.add_argument('index_cat', type=IndexCategory, choices=list(IndexCategory), help="index category")

    jkey_c = 'code_name'
    jkey_t = 'table_name'
    jkey_k = 'id'
    parser.add_argument("-c", default="{0}".format(jkey_c), help="the key for code name, default: {0}".format(jkey_c))
    parser.add_argument("-t", default="{0}".format(jkey_t), help="the key for table/mode name, default: {0}".format(jkey_t))
    parser.add_argument("-k", default="{0}".format(jkey_k), help="the key for key/gid/item id, default: {0}".format(jkey_k))
    parser.add_argument("-v", "--valkeys", action='append', help="the key for value/rule content, default: all")
    parser.add_argument("-lk", "--lowercase_key", action='store_true', help="lower case the all keys of the item, e.g. gid, goods_name, category_code and etc, default: false")
    parser.add_argument("-dt", "--datetimekey", help="source json key of datetime field for sorted set score")
    parser.add_argument("-ttl", "--ttl", type=int, default=259200, help='live time of keys')
    parser.add_argument("-d", "--deamon", action='store_true', help='start as deamon mode')

    subparsers = parser.add_subparsers(help='sub-command help')
    parser_pipe = subparsers.add_parser("pipe", help="sync all file with pipelining")
    parser_pipe.set_defaults(func = pipe_sync_file)

    parser_tail = subparsers.add_parser("tail", help="sync once file grows")
    parser_tail.set_defaults(func = tail_sync_file)
    parser_tail.add_argument('-se', '--startfromend', action='store_true', help='start sync from the new appending rows')
 
    args = parser.parse_args()

    if args.datetimekey:
        logger.warn('--datetimekey, the argument will cause data to be added into Sorted Set, i.e. zadd')

    if args.deamon:
        try:
            #-- fork a child process, return 0 in the child and the child process id in the parent.
            #   see https://docs.python.org/2/library/os.html#os.fork
            pid = os.fork()

            #-- kill the current process if now is parent
            if 0 != pid:
                sys.exit(0)
        except OSError as e:
            logger.error(e, exc_info=True)
 
#    print args
    args.func(args)

 
