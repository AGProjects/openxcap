CREATE TABLE subscriber (
    id INT(10) UNSIGNED AUTO_INCREMENT PRIMARY KEY NOT NULL,
    username VARCHAR(64) NOT NULL DEFAULT '',
    domain VARCHAR(64) NOT NULL DEFAULT '',
    password VARCHAR(25) NOT NULL DEFAULT '',
    ha1 VARCHAR(64) NOT NULL DEFAULT '',
    UNIQUE KEY user_id (username, domain),
    KEY username_id (username)
) ENGINE=InnoDB;

CREATE TABLE `xcap` (
  `id` int(10) NOT NULL auto_increment,
  `username` varchar(66) NOT NULL,
  `domain` varchar(128) NOT NULL,
  `doc` blob NOT NULL,
  `doc_type` int(11) NOT NULL,
  `etag` varchar(64) NOT NULL,
  `source` int(11) NOT NULL,
  `doc_uri` varchar(128) NOT NULL,
  `port` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `udd_xcap` (`username`,`domain`,`doc_type`,`doc_uri`)
) ENGINE=InnoDB;
