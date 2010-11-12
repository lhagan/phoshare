'''Prompt user for confirmations based on file names, and keeps track of 
   previous choices.
'''

import tilutil.systemutils as su

class ConfirmManager:
    '''Class to prompt user for file operation confirmations, and remember the 
       patterns for future prompts.
    '''

    def __init__(self):
        self.approve_list = []
        self.reject_list = []
    
    def addapprove(self, value):
        '''Add a value to the list of approved values'''
        self.approve_list.append(value)
    
    def confirm(self, path, message, choices): #IGNORE:R0911
        '''Prompts for confirmation.
        
        An item in the approve list always returns 1.
        An item in the reject list always returns 0.
        An empty response (hitting just enter) always returns 0.
        A response of +... adds a pattern to the approve list and returns 1.
        A response of -... adds a pattern to the reject list and returns 0.
        A response startring with y returns 1.
        The first character of any other response is matched against the letters
        in the choices parameters. If a match is found, the position is returned.
        For example, if choices is "nyc", entering c... returns 2.
        All other input returns 0.
        All matching is done without case sensitivity, and choices should be all
        lower case.
        
        @param theFile a <code>File</code> value
        @param message a <code>String</code> value
        @param choices a <code>String</code> value
        @return an <code>int</code> value
        '''
        for pattern in self.approve_list:
            if path.find(pattern) != -1:
                return 1
        
        for pattern in self.reject_list:
            if path.find(pattern) != -1:
                return 0
        
        answer = raw_input(su.fsenc(message))
        if len(answer) == 0:
            return 0
        first_char = answer[0].lower()
        if len(answer) > 1 and first_char == '+':
            self.approve_list.append(answer[1:])
            return 1
        
        if len(answer) > 1 and first_char == '-':
            self.reject_list.append(answer[1:])
            return 0
        
        if first_char == 'y':
            return 1
        
        for c in range(0, len(choices)):
            if first_char == choices[c]:
                return c
        return 0
