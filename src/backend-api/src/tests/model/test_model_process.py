import base64
import json
import pytest

# Adjust import path to match your project structure
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from routers.model.model_process import FileInfo, enlist_process_queue_response # noqa: E402


class TestFileInfo:
    """Test cases for FileInfo model"""

    def test_file_info_creation(self):
        """Test creating a FileInfo instance"""
        file_info = FileInfo(
            filename="test.yaml",
            content=b"test content",
            content_type="application/yaml",
            size=12,
        )

        assert file_info.filename == "test.yaml"
        assert file_info.content == b"test content"
        assert file_info.content_type == "application/yaml"
        assert file_info.size == 12

    def test_file_info_serialization_excludes_content(self):
        """Test that content is excluded from serialization"""
        file_info = FileInfo(
            filename="test.yaml",
            content=b"secret content",
            content_type="application/yaml",
            size=14,
        )

        serialized = file_info.model_dump()

        # Content should be excluded
        assert "content" not in serialized
        assert serialized["filename"] == "test.yaml"
        assert serialized["content_type"] == "application/yaml"
        assert serialized["size"] == 14

    def test_file_info_with_none_content(self):
        """Test FileInfo with None content"""
        file_info = FileInfo(
            filename="test.yaml", content=None, content_type="application/yaml", size=0
        )

        assert file_info.content is None
        assert file_info.size == 0

    @pytest.mark.parametrize(
        "filename,content_type,expected_size",
        [
            ("config.json", "application/json", 25),
            ("data.yaml", "application/yaml", 50),
            ("script.sh", "text/x-shellscript", 100),
            ("readme.md", "text/markdown", 200),
        ],
    )
    def test_file_info_parametrized(self, filename, content_type, expected_size):
        """Parametrized test for different file types"""
        content = b"x" * expected_size
        file_info = FileInfo(
            filename=filename,
            content=content,
            content_type=content_type,
            size=expected_size,
        )

        assert file_info.filename == filename
        assert file_info.content_type == content_type
        assert file_info.size == expected_size
        assert len(file_info.content) == expected_size


class TestEnlistProcessQueueResponse:
    """Test cases for enlist_process_queue_response model"""

    def test_response_creation(self):
        """Test creating a response instance"""
        files = [
            FileInfo(
                filename="test1.yaml",
                content=b"content1",
                content_type="application/yaml",
                size=8,
            ),
            FileInfo(
                filename="test2.yaml",
                content=b"content2",
                content_type="application/yaml",
                size=8,
            ),
        ]

        response = enlist_process_queue_response(
            message="Files uploaded successfully",
            process_id="123e4567-e89b-12d3-a456-426614174000",
            files=files,
        )

        assert response.message == "Files uploaded successfully"
        assert response.process_id == "123e4567-e89b-12d3-a456-426614174000"
        assert len(response.files) == 2

    def test_to_base64_basic(self):
        """Test basic to_base64 functionality"""
        files = [
            FileInfo(
                filename="test.yaml",
                content=b"test content",
                content_type="application/yaml",
                size=12,
            )
        ]

        response = enlist_process_queue_response(
            message="Test message", process_id="test-id", files=files
        )

        # Test the to_base64 method
        base64_result = response.to_base64()

        # Verify it's a valid base64 string
        assert isinstance(base64_result, str)
        assert len(base64_result) > 0

        # Should be valid base64 (no exception when decoding)
        try:
            base64.b64decode(base64_result)
        except Exception as e:
            pytest.fail(f"Invalid base64 string generated: {e}")

    def test_to_base64_content_exclusion(self):
        """Test that content is excluded from base64 serialization"""
        files = [
            FileInfo(
                filename="secret.yaml",
                content=b"super secret content that should not be serialized",
                content_type="application/yaml",
                size=50,
            )
        ]

        response = enlist_process_queue_response(
            message="Files with secret content", process_id="secret-test", files=files
        )

        # Get base64 and decode
        base64_result = response.to_base64()
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        # Verify content is excluded
        assert "content" not in decoded_json["files"][0]
        assert decoded_json["files"][0]["filename"] == "secret.yaml"
        assert decoded_json["files"][0]["content_type"] == "application/yaml"
        assert decoded_json["files"][0]["size"] == 50

    def test_to_base64_multiple_files(self):
        """Test to_base64 with multiple files"""
        files = [
            FileInfo(
                filename="ebs-kc-classes.yaml",
                content=b"apiVersion: v1\nkind: StorageClass",
                content_type="application/yaml",
                size=30,
            ),
            FileInfo(
                filename="ebs-kc-restore.yaml",
                content=b"apiVersion: v1\nkind: Pod",
                content_type="application/yaml",
                size=20,
            ),
            FileInfo(
                filename="config.json",
                content=b'{"database": "mongodb"}',
                content_type="application/json",
                size=23,
            ),
        ]

        response = enlist_process_queue_response(
            message="Multiple EKS files uploaded",
            process_id="eks-migration-123",
            files=files,
        )

        base64_result = response.to_base64()
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        assert decoded_json["message"] == "Multiple EKS files uploaded"
        assert decoded_json["process_id"] == "eks-migration-123"
        assert len(decoded_json["files"]) == 3

        # Check all files are properly serialized (without content)
        expected_files = [
            {
                "filename": "ebs-kc-classes.yaml",
                "content_type": "application/yaml",
                "size": 30,
            },
            {
                "filename": "ebs-kc-restore.yaml",
                "content_type": "application/yaml",
                "size": 20,
            },
            {"filename": "config.json", "content_type": "application/json", "size": 23},
        ]

        for i, expected in enumerate(expected_files):
            actual = decoded_json["files"][i]
            assert actual["filename"] == expected["filename"]
            assert actual["content_type"] == expected["content_type"]
            assert actual["size"] == expected["size"]
            assert "content" not in actual

    def test_to_base64_empty_files_list(self):
        """Test to_base64 with empty files list"""
        response = enlist_process_queue_response(
            message="No files uploaded", process_id="empty-process", files=[]
        )

        base64_result = response.to_base64()
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        assert decoded_json["message"] == "No files uploaded"
        assert decoded_json["process_id"] == "empty-process"
        assert decoded_json["files"] == []

    def test_to_base64_special_characters(self):
        """Test to_base64 with special characters and unicode"""
        files = [
            FileInfo(
                filename="test-файл.yaml",  # Cyrillic characters
                content=b"content with \xc3\xa9\xc3\xb1\xc3\xbc unicode",  # UTF-8 encoded special chars
                content_type="application/yaml",
                size=25,
            )
        ]

        response = enlist_process_queue_response(
            message="Special chars: éñüíçødé",
            process_id="unicode-test-123",
            files=files,
        )

        # Should handle special characters without error
        base64_result = response.to_base64()

        # Verify decoding works
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        assert decoded_json["message"] == "Special chars: éñüíçødé"
        assert decoded_json["process_id"] == "unicode-test-123"
        assert decoded_json["files"][0]["filename"] == "test-файл.yaml"

    def test_to_base64_large_response(self):
        """Test to_base64 with a large number of files"""
        files = []
        for i in range(100):  # Create 100 files
            files.append(
                FileInfo(
                    filename=f"file_{i:03d}.yaml",
                    content=b"x" * 1000,  # 1KB content each
                    content_type="application/yaml",
                    size=1000,
                )
            )

        response = enlist_process_queue_response(
            message="Bulk file upload", process_id="bulk-upload-test", files=files
        )

        base64_result = response.to_base64()

        # Should be able to handle large responses
        assert isinstance(base64_result, str)
        assert len(base64_result) > 0

        # Verify it decodes correctly
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        assert len(decoded_json["files"]) == 100
        assert decoded_json["message"] == "Bulk file upload"

    @pytest.mark.parametrize(
        "message,process_id",
        [
            ("", "test-id"),
            ("Test message", ""),
            ("", ""),
            ("Very long message " * 100, "very-long-process-id-" * 10),
        ],
    )
    def test_to_base64_edge_cases(self, message, process_id):
        """Test to_base64 with edge cases"""
        response = enlist_process_queue_response(
            message=message, process_id=process_id, files=[]
        )

        base64_result = response.to_base64()
        decoded_bytes = base64.b64decode(base64_result)
        decoded_json = json.loads(decoded_bytes.decode())

        assert decoded_json["message"] == message
        assert decoded_json["process_id"] == process_id


class TestIntegrationScenarios:
    """Integration tests simulating real-world usage scenarios"""

    def test_eks_migration_scenario(self):
        """Test EKS to AKS migration file upload scenario"""
        # Simulate EKS YAML files
        eks_files = [
            FileInfo(
                filename="ebs-kc-classes.yaml",
                content=b"""apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-csi-gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4""",
                content_type="application/yaml",
                size=150,
            ),
            FileInfo(
                filename="ebs-kc-restore.yaml",
                content=b"""apiVersion: v1
kind: Pod
metadata:
  name: restore-pod
spec:
  containers:
  - name: restore
    image: busybox""",
                content_type="application/yaml",
                size=120,
            ),
        ]

        response = enlist_process_queue_response(
            message="EKS migration files processed successfully",
            process_id="eks-migration-d173cea5-b1a5-4fab-929c-7379165cc96e",
            files=eks_files,
        )

        # Convert to base64 for queue message
        base64_queue_message = response.to_base64()

        # Verify the queue message can be decoded
        decoded = json.loads(base64.b64decode(base64_queue_message).decode())

        assert "EKS migration" in decoded["message"]
        assert "eks-migration-" in decoded["process_id"]
        assert len(decoded["files"]) == 2

        # Verify Kubernetes YAML files are properly handled
        filenames = [f["filename"] for f in decoded["files"]]
        assert "ebs-kc-classes.yaml" in filenames
        assert "ebs-kc-restore.yaml" in filenames


if __name__ == "__main__":
    # Enable VS Code integration with proper exit codes
    pytest.main([__file__, "-v", "--tb=short"])
