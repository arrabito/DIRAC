########################################################################
# $Id: $
########################################################################

"""
This class a wrapper around elasticsearch-py. It is used to query
Elasticsearch database.

"""

__RCSID__ = "$Id$"

from DIRAC                      import gLogger, S_OK, S_ERROR
from elasticsearch              import Elasticsearch
from elasticsearch_dsl          import Search
from elasticsearch.exceptions   import ConnectionError, TransportError
from datetime                   import datetime

class ElasticSearchDB( object ):
  
  """
  .. class:: ElasticSearchDB

  :param str url: the url to the database for example: el.cern.ch:9200
  :param str gDebugFile: is used to save the debug information to a file
  """
  
  __url = ""
  ########################################################################
  def __init__( self, host, port, debug = False ):
    """ c'tor
    :param self: self reference
    :param str host: name of the database for example: MonitoringDB
    :param str port: The full name of the database for example: 'Monitoring/MonitoringDB'
    :param bool debug: save the debug information to a file   
    """
    global gDebugFile
    
    if 'log' not in dir( self ):
      self.log = gLogger.getSubLogger( 'ElasticSearch' )
    self.logger = self.log
    
    self.__url = "http://%s:%s" % ( host, port )
        
    if debug:
      try:
        gDebugFile = open( "%s.debug.log" % self.__dbName, "w" )
      except IOError as e:
        self.log.error( e )
      
    self.__client = Elasticsearch( self.__url )
    self.__tryToConnect()
  
  ########################################################################  
  def query( self, query ):
    """It exexutes a query and it returns the result
    query is a dictionary. More info: search for elasticsearch dsl
    
    :param self: self reference
    :param dict query: It is the query in ElasticSerach DSL language
     
    """
    return self.__client.search( query )
  
  def __search(self, indexname):
    """
    it returns the object which can be used for reatriving ceratin value from the DB
    """
    return  Search(using = self.__client, index=indexname)
  
  ########################################################################
  def __tryToConnect( self ):
    """Before we use the database we try to connect and retrive the cluster name
    
    :param self: self reference
         
    """
    try:
      if self.__client.ping():
        result = self.__client.info()
        self.setClusterName ( result.get( "cluster_name", " " ) )
        self.log.info( "Database info", result )
        self._connected = True
      else:
        self.log.error( "Cannot connect to the database!" )
    except ConnectionError as e:
      self.log.error( e )
      self._connected = False 

  ########################################################################
  def getIndexes( self ):
    """
    It returns the available indexes...
    """
    return [ index for index in self.__client.indices.get_aliases() ]
  
  ########################################################################
  def getDocTypes( self, indexes ):
    try:
      result = self.__client.indices.get_mapping( indexes )
    except Exception as e:
      gLogger.error(e)
    doctype = ''
    for i in result:
      if len(result[i].get('mappings', {})) == 0:
        return S_ERROR("%s does not exists!" % indexes)
      doctype = result[i]['mappings']
      break
    return S_OK(doctype) 
  
  ########################################################################
  def checkIndex( self, indexName ):
    """
    it checks the existance of an index
    :param str indexName: the name of the index
    """
    return self.__client.indices.exists( indexName )
  
  ########################################################################
  def createFullIndexName( self, indexName ):
    """
    Given an index perfix we create the actual index name.
    :param str indexName: it is the name of the index
    """
    today = datetime.today().strftime( "%Y-%m-%d" )
    return "%s-%s" % ( indexName, today )
  
  def createIndex( self, indexPrefix, mapping ):
    """
    :param str indexPrefix: it is the index name. 
    :param dict mapping: the configuration of the index.
    
    """
    result = S_OK( "Index created" )
    fullIndex = self.createFullIndexName( indexPrefix )  # we have to create the an index in each day...
    try:
      self.log.info( "Create index: ", fullIndex + str( mapping ) )
      self.__client.indices.create( fullIndex, body = mapping )
    except Exception as e:
      result = S_ERROR( e )
    return result
    
  def getUniqueValue( self, indexName, key, orderBy = False ):
    """
    :param str indexName the name of the index which will be used for the query
    :param dict orderBy it is a dictionary in case we want to order the result {key:'desc'} or {key:'asc'} 
    It returns a list of unique value for a certain key from the dictionary.
    """
    
    s = self.__search( indexName )
    if orderBy:
      s.aggs.bucket( key, 'terms', field = key, size = 0, order = orderBy ).metric( key, 'cardinality', field = key )
    else:
      s.aggs.bucket( key, 'terms', field = key, size = 0 ).metric( key, 'cardinality', field = key )
    
    try:
      result = s.execute()
    except TransportError as e:
      return S_ERROR( e )
    
    values = []
    for i in result.aggregations[key].buckets:
      values += [i['key']]
    del s
    return S_OK( values )
