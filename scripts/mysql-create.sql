CREATE TABLE subscriber (
    id INT(10) UNSIGNED AUTO_INCREMENT PRIMARY KEY NOT NULL,
    username VARCHAR(64) NOT NULL DEFAULT '',
    domain VARCHAR(64) NOT NULL DEFAULT '',
    password VARCHAR(25) NOT NULL DEFAULT '',
    ha1 VARCHAR(64) NOT NULL DEFAULT '',
    UNIQUE KEY user_id (username, domain),
    KEY username_id (username)
) ENGINE=InnoDB;

CREATE TABLE `xcap_xml` (
  `id` int(10) NOT NULL auto_increment,
  `username` varchar(66) NOT NULL,
  `domain` varchar(128) NOT NULL,
  `xcap` text NOT NULL,
  `doc_type` int(11) NOT NULL,
  `etag` varchar(64) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `udd_xcap` (`username`,`domain`,`doc_type`)
) ENGINE=InnoDB;
