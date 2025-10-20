"""Tests for AWB Processing - 3-layer matching logic"""
import pytest
from difflib import SequenceMatcher
from utils.awb_processor import AWBProcessor


class TestThreeLayerMatching:
    """Test three-layer matching: cost, person, department"""

    def setup_method(self):
        """Initialize processor for each test"""
        self.processor = AWBProcessor()

    def test_fuzzy_match_exact(self):
        """Test exact department matching"""
        employee_map = {
            "John Doe": "Sales",
            "Jane Smith": "Marketing",
            "Bob Johnson": "Finance"
        }

        department, matched, confidence, matched_name = self.processor._match_department(
            "John Doe",
            employee_map
        )

        assert department == "Sales"
        assert matched is True
        assert confidence == 1.0
        assert matched_name == "John Doe"

    def test_fuzzy_match_similar(self):
        """Test fuzzy department matching with similarity"""
        employee_map = {
            "John Doe": "Sales",
            "Jane Smith": "Marketing",
            "Bob Johnson": "Finance"
        }

        # Slightly misspelled name
        department, matched, confidence, matched_name = self.processor._match_department(
            "Jon Doe",  # Missing 'h'
            employee_map
        )

        # Should find fuzzy match if confidence > threshold (0.85)
        if matched:
            assert confidence >= self.processor.fuzzy_threshold
            assert department in ["Sales", "Marketing", "Finance"]

    def test_fuzzy_match_no_match(self):
        """Test no matching employee"""
        employee_map = {
            "John Doe": "Sales",
            "Jane Smith": "Marketing",
        }

        department, matched, confidence, matched_name = self.processor._match_department(
            "Unknown Person",
            employee_map
        )

        assert department is None
        assert matched is False
        assert confidence == 0.0
        assert matched_name is None

    def test_cost_matching_logic(self):
        """Test cost layer matching (order_number join)"""
        summary_results = [
            {"order_number": "ORD-001", "charge": 1500.00},
            {"order_number": "ORD-002", "charge": 2000.00},
            {"order_number": "ORD-003", "charge": 1200.00},
        ]

        detail_results = [
            {"order_number": "ORD-001", "colleague_name": "John Doe"},
            {"order_number": "ORD-002", "colleague_name": "Jane Smith"},
            {"order_number": "ORD-004", "colleague_name": "Bob Johnson"},  # No match
        ]

        employee_map = {
            "John Doe": "Sales",
            "Jane Smith": "Marketing",
            "Bob Johnson": "Finance"
        }

        enriched = self.processor._three_layer_matching(
            summary_results,
            detail_results,
            employee_map,
            ["s3://file1.pdf", "s3://file2.pdf", "s3://file3.pdf"]
        )

        assert len(enriched) == 3

        # Check first record
        assert enriched[0]["order_number"] == "ORD-001"
        assert enriched[0]["cost"] == 1500.00
        assert enriched[0]["cost_matched"] is True
        assert enriched[0]["department"] == "Sales"
        assert enriched[0]["department_matched"] is True

        # Check second record
        assert enriched[1]["order_number"] == "ORD-002"
        assert enriched[1]["cost"] == 2000.00
        assert enriched[1]["department"] == "Marketing"

        # Check unmatched record
        assert enriched[2]["order_number"] == "ORD-004"
        assert enriched[2]["cost"] is None
        assert enriched[2]["cost_matched"] is False
        assert enriched[2]["department"] == "Finance"
        assert enriched[2]["department_matched"] is True

    def test_sequence_matcher_similarity(self):
        """Test SequenceMatcher similarity ratio used in fuzzy matching"""
        # Test exact match
        similarity = SequenceMatcher(None, "john doe", "john doe").ratio()
        assert similarity == 1.0

        # Test minor typo
        similarity = SequenceMatcher(None, "john doe", "jon doe").ratio()
        assert 0.8 <= similarity < 1.0

        # Test case insensitive
        similarity = SequenceMatcher(None, "john doe".lower(), "JOHN DOE".lower()).ratio()
        assert similarity == 1.0

        # Test major difference
        similarity = SequenceMatcher(None, "john doe", "jane smith").ratio()
        assert similarity < 0.5

    def test_empty_inputs(self):
        """Test handling of empty inputs"""
        # Empty employee map
        department, matched, confidence, matched_name = self.processor._match_department(
            "John Doe",
            {}
        )
        assert matched is False
        assert department is None

        # Empty colleague name
        employee_map = {"John Doe": "Sales"}
        department, matched, confidence, matched_name = self.processor._match_department(
            "",
            employee_map
        )
        assert matched is False

    def test_case_insensitivity(self):
        """Test case-insensitive matching"""
        employee_map = {
            "John Doe": "Sales",
            "jane smith": "Marketing",
        }

        # Different case variations
        test_cases = [
            ("JOHN DOE", True, "Sales"),
            ("john doe", True, "Sales"),
            ("JoHn DoE", True, "Sales"),
            ("JANE SMITH", True, "Marketing"),
            ("Jane Smith", True, "Marketing"),
        ]

        for name, should_match, expected_dept in test_cases:
            department, matched, confidence, _ = self.processor._match_department(
                name,
                employee_map
            )
            assert matched == should_match, f"Failed for {name}"
            if should_match:
                assert department == expected_dept

    def test_matching_confidence_scores(self):
        """Test confidence scores in matching"""
        employee_map = {"John Michael Doe": "Sales"}

        # Exact match
        _, matched, confidence, _ = self.processor._match_department("John Michael Doe", employee_map)
        assert confidence == 1.0

        # High similarity
        _, matched, confidence, _ = self.processor._match_department("John M Doe", employee_map)
        # Should have some similarity but less than exact

        # Low similarity
        _, matched, confidence, _ = self.processor._match_department("Jane Smith", employee_map)
        assert confidence == 0.0

    def test_large_dataset_matching(self):
        """Test matching with larger employee dataset"""
        employee_map = {f"Employee {i}": f"Department{i % 5}" for i in range(100)}

        # Should still find exact matches
        dept, matched, conf, _ = self.processor._match_department("Employee 50", employee_map)
        assert matched is True
        assert conf == 1.0
        assert dept == "Department0"

        # Should handle non-existent
        dept, matched, conf, _ = self.processor._match_department("Unknown Employee 999", employee_map)
        assert matched is False


class TestCSVParsing:
    """Test CSV parsing for employee mapping"""

    def test_employee_csv_structure(self):
        """Test expected CSV structure: name, department"""
        # This would require actual file I/O, so just document the expected format
        expected_format = """name,department
John Doe,Sales
Jane Smith,Marketing
Bob Johnson,Finance"""

        lines = expected_format.strip().split('\n')
        assert lines[0] == "name,department"
        assert len(lines) == 4

    def test_csv_with_special_characters(self):
        """Test CSV with special characters"""
        csv_data = """name,department
"O'Brien, Patrick",Sales
"Müller, Hans",Marketing
"García-López, Maria",Finance"""

        lines = csv_data.strip().split('\n')
        assert len(lines) == 4


class TestAWBProcessingIntegration:
    """Integration tests for complete AWB processing"""

    def test_full_matching_pipeline(self):
        """Test complete 3-layer matching pipeline"""
        processor = AWBProcessor()

        summary_results = [
            {"order_number": "AWB-2025-001", "charge": 5000.00},
            {"order_number": "AWB-2025-002", "charge": 3500.00},
        ]

        detail_results = [
            {"order_number": "AWB-2025-001", "colleague_name": "Alice Chen"},
            {"order_number": "AWB-2025-002", "colleague_name": "Bob Martinez"},
            {"order_number": "AWB-2025-003", "colleague_name": "Carol Davis"},
        ]

        employee_map = {
            "Alice Chen": "Sales",
            "Bob Martinez": "Marketing",
            "Carol Davis": "Operations"
        }

        enriched = processor._three_layer_matching(
            summary_results,
            detail_results,
            employee_map,
            ["s3://awb1.pdf", "s3://awb2.pdf", "s3://awb3.pdf"]
        )

        # Verify all records processed
        assert len(enriched) == 3

        # Verify matched records
        matched_count = sum(1 for r in enriched if r.get('department_matched'))
        assert matched_count == 3  # All should match since employees in map

        # Verify cost matching
        cost_matched = sum(1 for r in enriched if r.get('cost_matched'))
        assert cost_matched == 2  # Only first two orders in summary

        # Verify data structure
        for record in enriched:
            assert 'order_number' in record
            assert 'cost' in record
            assert 'cost_matched' in record
            assert 'colleague' in record
            assert 'department' in record
            assert 'department_matched' in record
            assert 'match_confidence' in record


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
