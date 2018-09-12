package com.venraas.msclient;

import java.io.IOException;
import java.util.Properties;

import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;


public class MSClient {	
	
	static JedisPool _jedisPool = null;		
		
		
	public static MSClient getInstance() {
		if (null == _jedisPool) {
			synchronized (MSClient.class) {
				if (null == _jedisPool) {
					_jedisPool = _init_jedisPool();
				}
			}
		}
		
		return new MSClient();
	}
	
	public Jedis jedis() {
		return _jedisPool.getResource();
	}
	
	private MSClient() { }
	
	private static JedisPool _init_jedisPool() {
		String host;
	    Integer port;
	    int pool_size;
	    	
	    Properties config = new Properties();
	    try {				    	
			config.load(
			    Thread.currentThread()
			        .getContextClassLoader()
			        .getResourceAsStream("application.properties"));
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
	    
	    host = config.getProperty("redis.host");
	    port = Integer.valueOf(config.getProperty("redis.port"));
	    pool_size = Integer.valueOf(config.getProperty("redis.pool_size", "256"));	    

	    JedisPoolConfig poolConfig = new JedisPoolConfig();	    
	    //-- Default : 8, consider how many concurrent connections into Redis you will need under load
	    poolConfig.setMaxTotal(pool_size);

	    _jedisPool = new JedisPool(poolConfig, host, port);					

		return _jedisPool;
	}
	
		
}
