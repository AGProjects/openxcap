#!/usr/bin/env python3

# Copyright (C) 2007-2025 AG-Projects.
#

from common import *

pidf_xml = """<?xml version='1.0' encoding='UTF-8'?>
        <presence xmlns='urn:ietf:params:xml:ns:pidf' 
                  xmlns:dm='urn:ietf:params:xml:ns:pidf:data-model' 
                  xmlns:rpid='urn:ietf:params:xml:ns:pidf:rpid'
                  xmlns:c='urn:ietf:params:xml:ns:pidf:cipid'
                  entity='sip:test@example.com'>
          <tuple id='xa432124'>
            <status>
              <basic>open</basic>
            </status>
          </tuple>
          <dm:person id='p57123abx'>
            <rpid:activities><rpid:unknown/></rpid:activities>
          </dm:person>
        </presence>"""


class PIDFTest(XCAPTest):

    def test_pidf_manipulation(self):
        self.getputdelete('pidf-manipulation', pidf_xml, 'application/pidf+xml')

if __name__ == '__main__':
    runSuiteFromModule()
