CREATE TABLE subscriber (
    id INTEGER NOT NULL AUTO_INCREMENT,
    username VARCHAR(64),
    domain VARCHAR(64),
    password VARCHAR(255),
    ha1 VARCHAR(64),
    PRIMARY KEY (id)
);

CREATE TABLE watchers (
    id INTEGER NOT NULL AUTO_INCREMENT,
    presentity_uri VARCHAR(255) NOT NULL,
    watcher_username VARCHAR(64) NOT NULL,
    watcher_domain VARCHAR(64) NOT NULL,
    event VARCHAR(64) NOT NULL,
    status INTEGER NOT NULL,
    reason VARCHAR(64),
    inserted_time INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT watcher_idx UNIQUE (presentity_uri, watcher_username, watcher_domain, event)
);

CREATE TABLE xcap (
    id INTEGER NOT NULL AUTO_INCREMENT,
    subscriber_id INTEGER,
    username VARCHAR(64) NOT NULL,
    domain VARCHAR(64) NOT NULL,
    doc BLOB NOT NULL,
    doc_type INTEGER NOT NULL,
    etag VARCHAR(64) NOT NULL,
    source INTEGER NOT NULL,
    doc_uri VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(subscriber_id) REFERENCES subscriber (id) ON DELETE CASCADE,
    CONSTRAINT account_doc_type_idx UNIQUE (username, domain, doc_type, doc_uri)
);

CREATE INDEX source_idx ON xcap (source);
CREATE INDEX xcap_subscriber_id_exists ON xcap (subscriber_id);
