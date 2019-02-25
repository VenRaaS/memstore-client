## Overview
![](https://drive.google.com/uc?id=1DsmJmeIIVFPmYGvf9rZ6f8xgNY1MitwI)

## Why we need [memorystore](https://cloud.google.com/memorystore/)
### Latency vs. Throughput with data tiers
![](https://drive.google.com/uc?id=1OcIYJ02gqUM2AGCT3mgAGrL63DO0jc-d)

### Relieving the bottleneck 
![](https://drive.google.com/uc?id=1zXixdFf2LS-YQEIK_6KkftpSVUBaaOyJ)

## Client

### [netcat](https://en.wikipedia.org/wiki/Netcat)
* connect to redis  
  `nc -v ${HOST} ${PORT}`, e.g. `nc -v ms-westernwall 6379`
* installation under ubuntu  
  `ubuntu - `apt-get install netcat`
* installation under centos  
  `yum install nc.x86_64`

### [redis-cli](https://redis.io/topics/rediscli)
* connect to redis  
  `redis-cli -h ${HOST} -p 6379`
* installation under Ubuntu  
  `apt-get install redis-tools`
* installation under Centos, [ref](https://www.linode.com/docs/databases/redis/install-and-configure-redis-on-centos-7/#install-redis)
  ```
  yum install epel-release
  yum install redis
  systemctl status redis    # redis should be disable 
  ```

### [jedis](https://github.com/xetorthio/jedis/wiki)

### [redis-py](https://github.com/andymccurdy/redis-py)

## Data type and commands
* [Strings](https://redis.io/topics/data-types#strings) - Redis Strings are binary safe.
  * [SET key value](https://redis.io/commands/set)
  * [GET key](https://redis.io/commands/get)
  * [APPEND key value](https://redis.io/commands/append)
  
* [Redis keys](https://redis.io/topics/data-types-intro#redis-keys)
  * [EXPIRE key seconds](https://redis.io/commands/expire)
  * [TTL key](https://redis.io/commands/ttl)
  * [SCAN cursor [MATCH pattern] [COUNT count]](https://redis.io/commands/scan)
    * [list of keys](https://redis.io/topics/rediscli#getting-a-list-of-keys)  
      `redis-cli -h $HOST --scan --pattern '*-11*'`
    * count the number of keys with the specific pattern, e.g.  
    `redis-cli -h {$HOST} --scan --pattern '*_mod/breadcrumb*' | wc -l`
  * [KEYS pattern](https://redis.io/commands/keys) 
    * **notice that** you should always consider ```scan``` instead of ```keys``` to prevent block redis server.    
  * [DEL key [key ...]](https://redis.io/commands/del)
    * del keys by specific pattern  
      `redis-cli -h ${HOST} --scan --pattern '*_mod*' | xargs redis-cli  -h ${HOST} del`   
      `redis-cli -h ${HOST} --scan --pattern '*_mod*' | xargs redis-cli  -h ${HOST} unlink` 
  * [FLUSHALL](https://redis.io/commands/flushall)
  
* [Lists](https://redis.io/topics/data-types#lists) - [Redis lists are implemented via Linked Lists](https://redis.io/topics/data-types-intro#redis-lists)
  * [LPUSH key value [value ...]](https://redis.io/commands/lpush)
  * [RPUSH key value [value ...]](https://redis.io/commands/rpush)
  * [LRANGE key start stop](https://redis.io/commands/lrange)
  * [LTRIM key start stop](https://redis.io/commands/ltrim)
  
* [Sorted sets](https://redis.io/topics/data-types-intro#redis-sorted-sets)
  * [ZADD key score member [score member ...]](https://redis.io/commands/zadd)
  * [ZRANGE key start stop [WITHSCORES]](https://redis.io/commands/zrange), lowest to the highest
  * [ZREVRANGE key start stop [WITHSCORES]](https://redis.io/commands/zrevrange), highest to the lowest
  * [ZREMRANGEBYRANK key start stop](https://redis.io/commands/zremrangebyrank)  
    `zremrangebyrank key 0 -4`, keep top 3 hightest scoring members.

## Key and value schema for data access in VenRaaS
### gocc
* goods / category
  * `["${code_name}_gocc_${date}", "${table_name}", "${id}"]` => [json]
  * ~~`/${code_name}_gocc_${date}/${table_name}/_search?q=${id_key}:${id}` => [json]~~
    * MS query format
      * `LRANGE $key 0 0`
    * Data format example
      * `["comp01_gocc_20190202", "goods", "gid01"]`
      * `["comp01_gocc_20190202", "category", "categ_code01"]`
  
### mod
* c2i_model / i2i_model / ...
  * `["${code_name}_mod_${date}", "${table_name}", "${id}"]` => [json]
  * ~~`/${code_name}_mod_${date}/${table_name}/_search?q=${id_key}:${id}` => [json]~~
    * MS query format
      * `LRANGE $key 0 0`
    * Data format example
      * `["comp01_mod_20190202", "tp", "categ_code01"]`
      * `["comp01_mod_20190202", "i2i_cooc", "gid01"]`
* goods_category_flatten
  * `["${code_name}_mod_${date}", "gcf", "${gid}"]` => [json, json, ...] 
  * ~~`/${code_name}_mod_${date}/goods_category_flatten/_search?q=gid:${gid}` => [json, json, ...]~~
    * MS query format
      * `LRANGE ${key} 0 -1`
    * Data format example
      * `["comp01_mod_20190202", "gcf", "gid01"]`
* breadcrumb
  * `["${code_name}_mod_${date}", "bc", "${gid}"]` => [json, json, ...]
  * ~~`/${code_name}_mod_${date}/breadcrumb/_search?q=gid:${gid}` => [json, json, ...]~~
    * MS query format
      * `LRANGE ${key} 0 -1`
    * Data format example
      * `["comp01_mod_20190202", "bc", "gid01"]`
### opp
* ~~`/${code_name}_opp/OnlinePref/_search_last_gop_ops?q=ven_guid:${ven_guid}` => [json_action(t), json_action(t-1), ... ]~~
  * ~~MS query format~~
    * ~~`LRANGE $key 0 -1`~~
* ~~`/${code_name}_opp/OnlinePref/_search_last_checkout_gids?q=ven_guid:${ven_guid}` => [{"trans_i": {"ilist": [{"id": "xxx"}], "id": "ooo"}}, ...]~~
  * ~~MS query format~~
    * ~~`LRANGE $key 0 -1`~~
#### action embedded version
* `["${code_name}_opp", "pageload", "${ven_guid}"]` => [json_action(t), json_action(t-1), ... ]
* ~~`/${code_name}_opp/OnlinePref/pageload/_search_last_gop_ops?q=ven_guid:${ven_guid}` => [json_action(t), json_action(t-1), ... ]~~
  * MS query format
    * `LRANGE $key 0 -1`
  * Data format example
    * `["comp01_opp", "pageload", "ven_guid01"]`
* `["${code_name}_opp", "checkout", "${ven_guid}"]` => [{"trans_i": {"ilist": [{"id": "xxx"}], "id": "ooo"}}, ...]
* ~~`/${code_name}_opp/OnlinePref/checkout/_search_last_checkout_gids?q=ven_guid:${ven_guid}` => [{"trans_i": {"ilist": [{"id": "xxx"}], "id": "ooo"}}, ...]~~
  * MS query format
    * `LRANGE $key 0 -1`
  * Data format example
    * `["comp01_opp", "checkout", "ven_guid01"]`
* `["${code_name}_opp", "unfavadd", "${ven_guid}"]` => [json_action(t), json_action(t-1), ... ]
* ~~`/${code_name}_opp/OnlinePref/unfavadd?q=ven_guid:${ven_guid}` => [json_action(t), json_action(t-1), ... ]~~
  * MS query format
    * `LRANGE $key 0 -1`
  * Data format example
    * `["comp01_opp", "unfavadd", "ven_guid01"]`

### oua, [sorted sets](https://redis.io/topics/data-types-intro#redis-sorted-sets) whcih is sorted by log datetime

* `["${code_name}_oua", "guid2uid", "${ven_guid}"]` => [{"uid": "201008168544"}, ...]
* ~~`/${code_name}_oua/OnlineUserAlign/_search_last_login_uid?q=ven_guid:${ven_guid}` => [{"uid": "201008168544"}, ...]~~
  * MS query format
    * `LRANGE ${key} 0 -1`
  * Data format example
    * `["comp01_oua", "guid2uid", "ven_guid01"]`
* `["${code_name}_oua", "uid2guids", "${uid}"]` => [{"ven_guid": "202004242347055333a8c010adf2cc"}, ...]
* ~~`/${code_name}_oua/OnlineUserAlign/_search_last_ven_guids?q=uid:${uid}` => [{"ven_guid": "202004242347055333a8c010adf2cc"}, ...]~~
  * MS query format
    * `ZRANGE ${key} 0 -1` gets ven_guids by the oldest first order
    * `ZREVRANGE ${key} 0 -1` gets ven_guids by the latest first order
  * Data format example
    * `["comp01_oua", "uid2guids", "uid01"]`

where `${id_name}` stands for id field name, e.g.gid, category_code, ..., and `${id}` is the value.

## [Redis configurations (Cloud Memorystore for Redis)](https://cloud.google.com/memorystore/docs/reference/redis-configs)
* [Maxmemory policies](https://cloud.google.com/memorystore/docs/reference/redis-configs#maxmemory_policies)

## Reference
* [Cloud Memorystore](https://cloud.google.com/memorystore/)
  * [Google’s Cloud Memorystore for Redis is now GA](https://techcrunch.com/2018/09/19/googles-cloud-memorystore-for-redis-is-now-generally-available/)
* [Connecting to a Redis Instance from a Compute Engine VM](https://cloud.google.com/memorystore/docs/redis/connect-redis-instance-gce)
* [An introduction to Redis data types and abstractions](https://redis.io/topics/data-types-intro)
* [Redis: under the hood](https://pauladamsmith.com/articles/redis-under-the-hood.html)
* [JSON String Escape / Unescape](https://www.freeformatter.com/json-escape.html)

