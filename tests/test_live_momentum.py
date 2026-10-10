import unittest
from live_momentum import momentum_diagnostic


class MomentumDiagnosticTests(unittest.TestCase):
    def test_matchfacts_canonical_structure(self):
        packet={'content': {'matchFacts': {'momentum': {'main': {'data': [
            {'minute': 2, 'value': -13.7}, {'minute': 1, 'value': 25.2},
            {'minute': 1, 'value': 31.2}]}}}}}
        result=momentum_diagnostic(packet)
        self.assertEqual(result['state'], 'observed')
        self.assertEqual(result['source_path'],'content.matchFacts.momentum')
        self.assertEqual(result['points'],[{'minute':1,'value':31.2},
                                           {'minute':2,'value':-13.7}])

    def test_alternative_actual_list_structure(self):
        doc={'content':{'momentum': [{'minute': 7, 'value': 18.0}]}}
        result=momentum_diagnostic(doc)
        self.assertEqual(result['state'],'observed')
        self.assertEqual(result['points'][0]['minute'],7)

    def test_integer_minute_encoded_as_float_is_valid(self):
        doc={'content':{'momentum':{'data':[{'minute':3.0,'value':17.4}]}}}
        self.assertEqual(momentum_diagnostic(doc)['points'],
                         [{'minute':3,'value':17.4}])

    def test_alternative_data_container(self):
        doc={'content':{'momentum':{'data':[{'minute':9,'value':-10}]}}}
        self.assertEqual(momentum_diagnostic(doc)['points'][0]['value'],-10.)

    def test_missing_not_filled_using_shots_or_possession(self):
        doc={'content':{'stats': {'Periods': {'All': {'stats': [
            {'title':'Shots on target','stats':[8,2]}]}}}}}
        result=momentum_diagnostic(doc)
        self.assertEqual(result['state'],'missing')
        self.assertEqual(result['points'],[])

    def test_diagnoses_unsupported_and_invalid_without_fake_values(self):
        self.assertEqual(momentum_diagnostic({'content':{'momentum':{'foo':'bar'}}})['state'],
                         'unsupported_shape')
        p={'content':{'matchFacts':{'momentum':{'main':{'data':[
            {'minute':12,'value':float('nan')}, {'minute':'18+1','value':30},
            {'minute':20,'value':float('inf')}, {'minute':0,'value':3}]}}}}}
        self.assertEqual(momentum_diagnostic(p)['state'],'no_valid_points')
        self.assertEqual(momentum_diagnostic(p)['points'],[])

    def test_does_not_accept_strings_or_arbitrary_team_stats(self):
        self.assertEqual(momentum_diagnostic({'content':{'momentum':'42'}})['state'],
                         'unsupported_shape')
        self.assertEqual(momentum_diagnostic({'content':{'momentum':[
            {'minute':10,'home':50,'away':20}]}})['state'],'no_valid_points')


if __name__=='__main__':
    unittest.main()
