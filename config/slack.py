"""
Slack通知設定
メールアドレスとSlackの対応関係を管理
"""
import os

SLACK_CONFIG = {
    'k-mizutani@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_MIZUTANI',  # 環境変数名
        'mention': 'U07LY8DGGRJ'  # メンションするユーザーID
    },
    'kuze@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_KUZE',  # 環境変数名
        'mention': 'U05E3DUBB37'
    },
    'iwasaki@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_IWASAKI',  # 環境変数名
        'mention': 'U05HXCYF4BG'
    },
    'akase@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_AKASE',  # 環境変数名
        'mention': 'U05FNC60W2V'
    },
    'fujimori@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_FUJIMORI',  # 環境変数名
        'mention': 'U05E3DU12J1'
    },
    'y-suzuki@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_YSUZUKI',  # 環境変数名
        'mention': 'U086A7WTMKN'
    },
    'fujimura@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_FUJIMURA',  # 環境変数名
        'mention': 'U05RQNU7BFC'
    },
    'y-lim@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_YLIM',  # 環境変数名
        'mention': 'U09L7TC57GB'
    },
    'ma-immedio@miraiarc.jp': {
        'webhook_url_env': 'SLACK_WEBHOOK_MA_IMMEDIO',  # 環境変数名
        'mention': 'here'
    }
}


def get_slack_config(email: str) -> dict:
    """
    メールアドレスからSlack設定を取得
    
    Args:
        email: ユーザーのメールアドレス
    
    Returns:
        Slack設定（webhook_urlとmentionを含む辞書）
    """
    # 設定を取得
    config = SLACK_CONFIG.get(email, SLACK_CONFIG['ma-immedio@miraiarc.jp'])
    
    # 環境変数からwebhook URLを取得
    webhook_url_env = config['webhook_url_env']
    webhook_url = os.getenv(webhook_url_env)
    
    if not webhook_url:
        raise ValueError(f"環境変数 {webhook_url_env} が設定されていません")
    
    return {
        'webhook_url': webhook_url,
        'mention': config['mention']
    }


