from pathlib import Path


def load_prompt(prompt_file_name):
    prompt_path = Path(__file__).parents[2] / 'doc' / 'prompts' / f'{prompt_file_name}.prompt'
    return prompt_path.read_text(encoding='utf-8')

if __name__ == '__main__':
    ret = load_prompt('extend_keywords_for_column_recall')
    print(ret)