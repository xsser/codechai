from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import GitLoader
from git import Repo
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import os
import argparse

def detect_main_language(repo_path):
    file_extensions = {}
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            _, extension = os.path.splitext(file)
            if extension:
                file_extensions[extension] = file_extensions.get(extension, 0) + 1

    if file_extensions:
        return max(file_extensions, key=file_extensions.get)
    return None

def run_qa_bot(repo_url=None, repo_path=None, branch=None, file_extensions=None,
               relative_path=None, max_characters=190000, llm_provider="anthropic",
               api_key=None, model='claude-3-haiku-20240307', temperature=0, max_tokens=4000,
               openai_api_base=None, openai_model=None):

    if repo_url is None and repo_path is None:
        raise ValueError("请提供有效的 repo_url 或 repo_path 参数")

    if api_key is None:
        raise ValueError("请提供有效的 API key")

    if repo_url:
        temp_dir = "./temp_repo"
        os.makedirs(temp_dir, exist_ok=True)
        repo = Repo.clone_from(repo_url, to_path=temp_dir)
        repo_path = temp_dir
    else:
        repo = Repo(repo_path)

    branch = branch or repo.head.reference
    repo.git.checkout(branch)

    if not file_extensions:
        file_extensions = detect_main_language(repo_path) or ('.py', '.js', '.java', '.cpp', '.c', '.go', '.rb', '.php')

    file_filter = lambda file_path: file_path.endswith(file_extensions)

    loader_params = {
        'repo_path': repo_path,
        'branch': branch,
        'file_filter': file_filter
    }
    # 如果 relative_path 提供且非空,则加入参数中
    if relative_path:
        loader_params['relative_path'] = relative_path

    loader = GitLoader(**loader_params)
    documents = loader.load()
    documents_str = "".join(doc.page_content for doc in documents)

    if len(documents_str) > max_characters:
        print(f'文档总长度为:{len(documents_str)},已经超过api最大的token数量,请指定目录或者更换对应的llm api')
        documents_str = documents_str[:max_characters]

    if llm_provider == "anthropic":
        llm = ChatAnthropic(anthropic_api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    elif llm_provider == "openai":
        openai_kwargs = {'openai_api_key': api_key, 'temperature': temperature}
        if openai_api_base:
            openai_kwargs['openai_api_base'] = openai_api_base
        if model:
            openai_kwargs['model'] = model
        llm = ChatOpenAI(**openai_kwargs)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {llm_provider}")

    memory = ConversationBufferMemory(k=10)
    prompt_template = "Context: {input}"
    prompt = PromptTemplate(input_variables=["input"], template=prompt_template)

    llm_chain = LLMChain(llm=llm, prompt=prompt, memory=memory)

    while True:
        question = input("问题: ")
        input_str = f"Documents:\n{documents_str}\n\nQuestion: 结合以上的代码,请用中文回答我以下问题。{question}"
        result = llm_chain.predict(input=input_str)
        print(f"答案: {result}")

if __name__ == '__main__':

    # run_qa_bot(repo_path="./github_codes/langchain",
    #            llm_provider="anthropic",
    #            relative_path=['libs/core/langchain_core/document_loaders'],
    #            api_key="sk-or-v1-f134a4572cf15c0f459b3283cd58f4c4c37b48a92eec161af6d4e471e9207e1",
    #            model="claude-3-haiku-20240307")

    parser = argparse.ArgumentParser(description="CodeChai - “Chai”取自汉语中的“斋”，意指修身养性之地，传统上用于表示学问或技艺的研习场所，如“书斋”、“茶斋”。 ")
    parser.add_argument('--repo_url', type=str, help='git clone 远程下载的仓库')
    parser.add_argument('--repo_path', type=str, help='本地目录')
    parser.add_argument('--branch', type=str, help='分支')
    parser.add_argument('--relative_path', type=lambda s: s.split(','),
                        help='指定加载目录(部分仓库代码太大，可能会导致超过llm api加载token限制)')

    parser.add_argument('--max_characters', type=int, default=190000, help='指定最大的llm token数量')
    parser.add_argument('--llm_provider', type=str, default='anthropic', choices=['anthropic', 'openai'],
                        help='LLM 类型')
    parser.add_argument('--api_key', type=str, required=True, help='apikey')
    parser.add_argument('--model', type=str, default='claude-3-haiku-20240307',
                        help='模型名字')
    parser.add_argument('--temperature', type=float, default=0, help='模型的temperature参数')
    parser.add_argument('--max_tokens', type=int, default=4000, help='最大的单次llm api请求参数，和max_characters有区别')
    parser.add_argument('--openai_api_base', type=str, help='OpenAI API base URL，支持openroute等自定义模型')

    args = parser.parse_args()

    run_qa_bot(repo_url=args.repo_url,
               repo_path=args.repo_path,
               branch=args.branch,
               relative_path=args.relative_path,
               max_characters=args.max_characters,
               llm_provider=args.llm_provider,
               api_key=args.api_key,
               model=args.model,
               temperature=args.temperature,
               max_tokens=args.max_tokens,
               openai_api_base=args.openai_api_base)

