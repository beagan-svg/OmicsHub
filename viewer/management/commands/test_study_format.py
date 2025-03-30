import json
from django.core.management.base import BaseCommand
from viewer.management.commands.load_test_data import clean_study_set

class Command(BaseCommand):
    help = 'Test the study format cleaning function with various inputs'

    def handle(self, *args, **options):
        test_cases = [
            # Lists
            (["HMBA_Cross_Species"], "HMBA_Cross_Species"),
            (["HMBA_Human_Atlas", "HMBA_Human_Atlas_Cx"], "HMBA_Human_Atlas+HMBA_Human_Atlas_Cx"),
            ([], ""),
            ([""], ""),
            
            # Strings with JSON formatting
            ('["HMBA_Cross_Species"]', "HMBA_Cross_Species"),
            ('["HMBA_Human_Atlas+HMBA_Human_Atlas_Cx"]', "HMBA_Human_Atlas+HMBA_Human_Atlas_Cx"),
            ('[]', ""),
            
            # Regular strings
            ("HMBA_Cross_Species", "HMBA_Cross_Species"),
            ("HMBA_Human_Atlas+HMBA_Human_Atlas_Cx", "HMBA_Human_Atlas+HMBA_Human_Atlas_Cx"),
            ("", ""),
            
            # Edge cases
            (None, ""),
            (123, "123"),  # Non-string, non-list value
        ]
        
        self.stdout.write(self.style.SUCCESS('Testing study format cleaning function:'))
        self.stdout.write('=' * 80)
        
        for i, (input_value, expected_output) in enumerate(test_cases, 1):
            result = clean_study_set(input_value)
            success = result == expected_output
            
            status = self.style.SUCCESS('PASS') if success else self.style.ERROR('FAIL')
            
            self.stdout.write(f"Test {i}: {status}")
            self.stdout.write(f"  Input:    {repr(input_value)}")
            self.stdout.write(f"  Expected: {repr(expected_output)}")
            self.stdout.write(f"  Result:   {repr(result)}")
            self.stdout.write('-' * 80)
        
        # Test with an actual JSON-like string that might come from the database
        complex_test = '["BICAN_Dev_Atlas+BICAN_Dev_P10"]'
        expected = "BICAN_Dev_Atlas+BICAN_Dev_P10"
        result = clean_study_set(complex_test)
        success = result == expected
        
        status = self.style.SUCCESS('PASS') if success else self.style.ERROR('FAIL')
        self.stdout.write(f"Complex Test: {status}")
        self.stdout.write(f"  Input:    {repr(complex_test)}")
        self.stdout.write(f"  Expected: {repr(expected)}")
        self.stdout.write(f"  Result:   {repr(result)}")
        self.stdout.write('=' * 80) 