## Overview
![](https://drive.google.com/uc?id=1DsmJmeIIVFPmYGvf9rZ6f8xgNY1MitwI)

## Why we need [memorystore](https://cloud.google.com/memorystore/)
###
![](https://drive.google.com/uc?id=1OcIYJ02gqUM2AGCT3mgAGrL63DO0jc-d)

### 
![](https://drive.google.com/uc?id=1fSJGWi8HRahDr2XW3Q_bKNqlkruCFtmQ)

## Client

### [netcat](https://en.wikipedia.org/wiki/Netcat)
`nc -v ${HOST} ${PORT}`

### [redis-cli](https://redis.io/topics/rediscli)
* installation under Ubuntu  
  `apt-get install redis-tools`
  
`redis-cli -h ${HOST} -p 6379`

### [redis-py](https://github.com/andymccurdy/redis-py)

## Data type and commands
* [Strings](https://redis.io/topics/data-types#strings)
  * [SET key value](https://redis.io/commands/set)
  * [GET key](https://redis.io/commands/get)
  * [APPEND key value](https://redis.io/commands/append)
  
* [Redis keys](https://redis.io/topics/data-types-intro#redis-keys)
  * [EXPIRE key seconds](https://redis.io/commands/expire)
  * [TTL key](https://redis.io/commands/ttl)
  * [SCAN cursor [MATCH pattern] [COUNT count]](https://redis.io/commands/scan)
  * [KEYS pattern](https://redis.io/commands/keys)
  * [FLUSHALL](https://redis.io/commands/flushall)
  
* [Lists](https://redis.io/topics/data-types#lists) - [Redis lists are implemented via Linked Lists](https://redis.io/topics/data-types-intro#redis-lists)
  * [LPUSH key value [value ...]](https://redis.io/commands/lpush)
  * [RPUSH key value [value ...]](https://redis.io/commands/rpush)
  * [LRANGE key start stop](https://redis.io/commands/lrange)
  * [LTRIM key start stop](https://redis.io/commands/ltrim)

## Reference
* [Cloud Memorystore](https://cloud.google.com/memorystore/)
* [Connecting to a Redis Instance from a Compute Engine VM](https://cloud.google.com/memorystore/docs/redis/connect-redis-instance-gce)

