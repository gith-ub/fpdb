#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Copyright 2008, Carl Gherardi
#    
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#    
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#    
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
########################################################################

import sys
import logging
from HandHistoryConverter import *

# Betfair HH format

class Betfair(HandHistoryConverter):

    # Static regexes
    re_GameInfo      = re.compile("^(?P<LIMIT>NL|PL|) (?P<CURRENCY>\$|)?(?P<SB>[.0-9]+)/\$?(?P<BB>[.0-9]+) (?P<GAME>(Texas Hold\'em|Omaha Hi|Razz))", re.MULTILINE)
    re_SplitHands    = re.compile(r'\n\n+')
    re_HandInfo      = re.compile("\*\*\*\*\* Betfair Poker Hand History for Game (?P<HID>[0-9]+) \*\*\*\*\*\n(?P<LIMIT>NL|PL|) (?P<CURRENCY>\$|)?(?P<SB>[.0-9]+)/\$?(?P<BB>[.0-9]+) (?P<GAMETYPE>(Texas Hold\'em|Omaha Hi|Razz)) - (?P<DATETIME>[a-zA-Z]+, [a-zA-Z]+ \d+, \d\d:\d\d:\d\d GMT \d\d\d\d)\nTable (?P<TABLE>[ a-zA-Z0-9]+) \d-max \(Real Money\)\nSeat (?P<BUTTON>[0-9]+)", re.MULTILINE)
    re_Button        = re.compile(ur"^Seat (?P<BUTTON>\d+) is the button", re.MULTILINE)
    re_PlayerInfo    = re.compile("Seat (?P<SEAT>[0-9]+): (?P<PNAME>.*)\s\(\s(\$(?P<CASH>[.0-9]+)) \)")
    re_Board         = re.compile(ur"\[ (?P<CARDS>.+) \]")

    def __init__(self, in_path = '-', out_path = '-', follow = False, autostart=True):
        """\
in_path   (default '-' = sys.stdin)
out_path  (default '-' = sys.stdout)
follow :  whether to tail -f the input"""
        HandHistoryConverter.__init__(self, in_path, out_path, sitename="Betfair", follow=follow) # Call super class init.
        logging.info("Initialising Betfair converter class")
        self.filetype = "text"
        self.codepage = "cp1252"
        if autostart:
            self.start()


    def compilePlayerRegexs(self,  hand):
        players = set([player[1] for player in hand.players])
        if not players <= self.compiledPlayers: # x <= y means 'x is subset of y'
            # we need to recompile the player regexs.
            self.compiledPlayers = players
            player_re = "(?P<PNAME>" + "|".join(map(re.escape, players)) + ")"
            logging.debug("player_re: " + player_re)
            self.re_PostSB          = re.compile("^%s posts small blind \[\$?(?P<SB>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_PostBB          = re.compile("^%s posts big blind \[\$?(?P<BB>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_Antes           = re.compile("^%s antes asdf sadf sadf" % player_re, re.MULTILINE)
            self.re_BringIn         = re.compile("^%s antes asdf sadf sadf" % player_re, re.MULTILINE)
            self.re_PostBoth        = re.compile("^%s posts small \& big blinds \[\$?(?P<SBBB>[.0-9]+)" % player_re, re.MULTILINE)
            self.re_HeroCards       = re.compile("^Dealt to %s \[ (?P<CARDS>.*) \]" % player_re, re.MULTILINE)
            self.re_Action          = re.compile("^%s (?P<ATYPE>bets|checks|raises to|raises|calls|folds)(\s\[\$(?P<BET>[.\d]+)\])?" % player_re, re.MULTILINE)
            self.re_ShowdownAction  = re.compile("^%s shows \[ (?P<CARDS>.*) \]" % player_re, re.MULTILINE)
            self.re_CollectPot      = re.compile("^%s wins \$(?P<POT>[.\d]+) (.*?\[ (?P<CARDS>.*?) \])?" % player_re, re.MULTILINE)
            self.re_SitsOut         = re.compile("^%s sits out" % player_re, re.MULTILINE)
            self.re_ShownCards      = re.compile(r"%s (?P<SEAT>[0-9]+) (?P<CARDS>adsfasdf)" % player_re, re.MULTILINE)

    def readSupportedGames(self):
        return [["ring", "hold", "nl"]
               ]

    def determineGameType(self, handText):
        info = {'type':'ring'}

        m = self.re_GameInfo.search(handText)
        if not m:
            logging.info('GameInfo regex did not match')
            return None

        mg = m.groupdict()

        # translations from captured groups to our info strings
        limits = { 'NL':'nl', 'PL':'pl', 'Limit':'fl' }
        games = {              # base, category
                  "Texas Hold'em" : ('hold','holdem'),
                       'Omaha Hi' : ('hold','omahahi'),
                           'Razz' : ('stud','razz'),
                    '7 Card Stud' : ('stud','studhi')
               }
        currencies = { u' €':'EUR', '$':'USD', '':'T$' }
        if 'LIMIT' in mg:
            info['limitType'] = limits[mg['LIMIT']]
        if 'GAME' in mg:
            (info['base'], info['category']) = games[mg['GAME']]
        if 'SB' in mg:
            info['sb'] = mg['SB']
        if 'BB' in mg:
            info['bb'] = mg['BB']
        if 'CURRENCY' in mg:
            info['currency'] = currencies[mg['CURRENCY']]
        # NB: SB, BB must be interpreted as blinds or bets depending on limit type.

        return info

    def readHandInfo(self, hand):
        m = self.re_HandInfo.search(hand.handText)
        if(m == None):
            logging.info("Didn't match re_HandInfo")
            logging.info(hand.handText)
            return None
        logging.debug("HID %s, Table %s" % (m.group('HID'),  m.group('TABLE')))
        hand.handid = m.group('HID')
        hand.tablename = m.group('TABLE')
        hand.starttime = time.strptime(m.group('DATETIME'), "%A, %B %d, %H:%M:%S GMT %Y")
        #hand.buttonpos = int(m.group('BUTTON'))

    def readPlayerStacks(self, hand):
        m = self.re_PlayerInfo.finditer(hand.handText)
        for a in m:
            hand.addPlayer(int(a.group('SEAT')), a.group('PNAME'), a.group('CASH'))

        #Shouldn't really dip into the Hand object, but i've no idea how to tell the length of iter m
        if len(hand.players) < 2:
            logging.info("readPlayerStacks: Less than 2 players found in a hand")

    def markStreets(self, hand):
        m =  re.search(r"\*\* Dealing down cards \*\*(?P<PREFLOP>.+(?=\*\* Dealing Flop \*\*)|.+)"
                       r"(\*\* Dealing Flop \*\*(?P<FLOP> \[ \S\S, \S\S, \S\S \].+(?=\*\* Dealing Turn \*\*)|.+))?"
                       r"(\*\* Dealing Turn \*\*(?P<TURN> \[ \S\S \].+(?=\*\* Dealing River \*\*)|.+))?"
                       r"(\*\* Dealing River \*\*(?P<RIVER> \[ \S\S \].+))?", hand.handText,re.DOTALL)

        hand.addStreets(m)
            

    def readCommunityCards(self, hand, street): # street has been matched by markStreets, so exists in this hand
        if street in ('FLOP','TURN','RIVER'):   # a list of streets which get dealt community cards (i.e. all but PREFLOP)
            m = self.re_Board.search(hand.streets[street])
            hand.setCommunityCards(street, m.group('CARDS').split(', '))

    def readBlinds(self, hand):
        try:
            m = self.re_PostSB.search(hand.handText)
            hand.addBlind(m.group('PNAME'), 'small blind', m.group('SB'))
        except: # no small blind
            hand.addBlind(None, None, None)
        for a in self.re_PostBB.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'big blind', a.group('BB'))
        for a in self.re_PostBoth.finditer(hand.handText):
            hand.addBlind(a.group('PNAME'), 'small & big blinds', a.group('SBBB'))

    def readAntes(self, hand):
        logging.debug("reading antes")
        for player in m:
            logging.debug("hand.addAnte(%s,%s)" %(player.group('PNAME'), player.group('ANTE')))
            hand.addAnte(player.group('PNAME'), player.group('ANTE'))

    def readBringIn(self, hand):
        m = self.re_BringIn.search(hand.handText,re.DOTALL)
        if m:
            logging.debug("Player bringing in: %s for %s" %(m.group('PNAME'),  m.group('BRINGIN')))
            hand.addBringIn(m.group('PNAME'),  m.group('BRINGIN'))
        else:
            logging.warning("No bringin found")

    def readButton(self, hand):
        hand.buttonpos = int(self.re_Button.search(hand.handText).group('BUTTON'))

    def readHeroCards(self, hand):
        m = self.re_HeroCards.search(hand.handText)
        if(m == None):
            #Not involved in hand
            hand.involved = False
        else:
            hand.hero = m.group('PNAME')
            # "2c, qh" -> set(["2c","qc"])
            # Also works with Omaha hands.
            cards = m.group('CARDS')
            cards = [c.strip() for c in cards.split(',')]
            hand.addHoleCards(cards, m.group('PNAME'))

    def readStudPlayerCards(self, hand, street):
        # balh blah blah
        pass

    def readAction(self, hand, street):
        m = self.re_Action.finditer(hand.streets[street])
        for action in m:
            if action.group('ATYPE') == 'raises to':
                hand.addRaiseTo( street, action.group('PNAME'), action.group('BET') )
#            elif action.group('ATYPE') == ' completes it to':
#                hand.addComplete( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == 'calls':
                hand.addCall( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == 'bets':
                hand.addBet( street, action.group('PNAME'), action.group('BET') )
            elif action.group('ATYPE') == 'folds':
                hand.addFold( street, action.group('PNAME'))
            elif action.group('ATYPE') == 'checks':
                hand.addCheck( street, action.group('PNAME'))
            else:
                print "DEBUG: unimplemented readAction: '%s' '%s'" %(action.group('PNAME'),action.group('ATYPE'),)


    def readShowdownActions(self, hand):
        for shows in self.re_ShowdownAction.finditer(hand.handText):
            cards = shows.group('CARDS')
            cards = cards.split(', ')
            hand.addShownCards(cards, shows.group('PNAME'))

    def readCollectPot(self,hand):
        for m in self.re_CollectPot.finditer(hand.handText):
            hand.addCollectPot(player=m.group('PNAME'),pot=m.group('POT'))

    def readShownCards(self,hand):
        for m in self.re_ShownCards.finditer(hand.handText):
            if m.group('CARDS') is not None:
                cards = m.group('CARDS')
                cards = cards.split(', ')
                hand.addShownCards(cards=None, player=m.group('PNAME'), holeandboard=cards)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="ipath", help="parse input hand history", default="regression-test-files/betfair/befair.02.04.txt")
    parser.add_option("-o", "--output", dest="opath", help="output translation to", default="-")
    parser.add_option("-f", "--follow", dest="follow", help="follow (tail -f) the input", action="store_true", default=False)
    parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.CRITICAL, dest="verbosity", default=logging.INFO)
    parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.INFO, dest="verbosity")
    parser.add_option("--vv",
                  action="store_const", const=logging.DEBUG, dest="verbosity")

    (options, args) = parser.parse_args()

    LOG_FILENAME = './logging.out'
    logging.basicConfig(filename=LOG_FILENAME,level=options.verbosity)

    e = Betfair(in_path = options.ipath, out_path = options.opath, follow = options.follow)
