from src.libs.base.AppConfiguration import semantic_kernel_settings


def test_semantic_kernel_settings():
    assert semantic_kernel_settings.global_llm_service == "AzureOpenAI"
