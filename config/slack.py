"""
Slack通知設定
メールアドレスとSlackの対応関係を管理
"""

SLACK_CONFIG = {
    'k-mizutani@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U07LY8DGGRJ'  # メンションするユーザーID
    },
    'kuze@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U05E3DUBB37'
    },
    'iwasaki@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U05HXCYF4BG'
    },
    'akase@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U05FNC60W2V'
    },
    'fujimori@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U05E3DU12J1'
    },
    'y-suzuki@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U086A7WTMKN'
    },
    'fujimura@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
        'mention': 'U05RQNU7BFC'
    },
    'ma-immedio@miraiarc.jp': {
        'webhook_url': 'https://hooks.slack.com/services/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',  # 通知先チャンネル
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
    # 直接指定されている場合
    if email in SLACK_CONFIG:
        return SLACK_CONFIG[email]
    
    # 担当者なしの場合のデフォルト設定
    return SLACK_CONFIG['ma-immedio@miraiarc.jp']

