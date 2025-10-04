# 🏢 社内文書検索システム

LangChainとStreamlitを使用した社内文書検索・問い合わせシステムです。

## 🚀 機能

- **社内文書検索**: 関連する社内文書のありかを検索
- **社内問い合わせ**: 質問に対して社内文書をもとにAIが回答
- **多形式対応**: PDF、DOCX、TXT、CSVファイルに対応
- **部署別従業員検索**: 部署ごとの従業員情報を一覧表示

## 🛠️ 技術スタック

- **フレームワーク**: Streamlit
- **AI/LLM**: OpenAI GPT-4o-mini
- **ベクターDB**: Chroma
- **文書処理**: LangChain
- **データ処理**: Pandas

## 📋 セットアップ

### ローカル環境

1. リポジトリをクローン
```bash
git clone https://github.com/kentaro-seki/company_inner_search_app.git
cd company_inner_search_app
```

2. 仮想環境の作成と有効化
```bash
python -m venv env
source env/bin/activate  # Windowsの場合: env\Scripts\activate
```

3. 依存関係のインストール
```bash
pip install -r requirements.txt
```

4. OpenAI APIキーの設定
```bash
# .envファイルを作成
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

5. アプリケーションの起動
```bash
streamlit run main.py
```

### Streamlit Community Cloud

1. GitHubリポジトリをフォーク
2. [Streamlit Community Cloud](https://share.streamlit.io/)でデプロイ
3. Secretsで環境変数を設定:
   ```toml
   OPENAI_API_KEY = "your-openai-api-key-here"
   ```

## 📁 プロジェクト構造

```
├── main.py                 # メインアプリケーション
├── components.py          # UI コンポーネント
├── utils.py               # ユーティリティ関数
├── constants.py           # 定数・設定
├── initialize.py          # 初期化処理
├── requirements.txt       # 依存関係
├── data/                  # 社内文書データ
│   ├── MTG議事録/
│   ├── サービスについて/
│   ├── 会社について/
│   ├── 顧客について/
│   └── 社員について/
└── logs/                  # ログファイル
```

## 🔧 主な改善点

- **ページ番号表示**: (ページNo.X) 形式での統一表示
- **TXTファイル対応**: 議事録ルールなどのテキストファイル検索
- **部署別統合**: CSV従業員データの部署別グループ化
- **検索精度向上**: キーワード強化とドキュメント構造最適化

## 🚀 使用方法

1. **サイドバーで利用目的を選択**
   - 「社内文書検索」: 関連文書のありかを検索
   - 「社内問い合わせ」: AIによる質問回答

2. **検索例**
   - 社内文書検索: "社員の育成方針に関するMTGの議事録"
   - 社内問い合わせ: "人事部に所属している従業員情報を一覧化して"

## 📊 システム特徴

- **9名の人事部従業員**: 部署別統合により全員を漏れなく表示
- **多様な文書形式**: PDF、DOCX、TXT、CSVを統合検索
- **会話履歴機能**: 過去の質問を考慮した検索
- **日本語対応**: 完全な日本語文書処理

## 🔒 セキュリティ

- OpenAI APIキーは環境変数で管理
- ログファイルや機密情報は.gitignoreで除外
- Streamlit Secretsによる安全な本番環境設定