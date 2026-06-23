# eBay仕入れ判定・利益計算ツール

結論: Streamlit、Supabase、無料為替APIで動く、個人事業者向けの仕入れ前チェックツールです。

このツールは利益予測用です。実際のeBay手数料、配送可否、関税、DDP、検疫、規約適合性を保証しません。最終判断前に、eBay公式情報、配送会社公式料金、各国の禁制品・検疫情報を必ず確認してください。

## 主な機能

- アメリカ / オーストラリア向けの販売国切り替え
- USD/JPY、AUD/JPYの為替取得
- 為替バッファを引いた安全側レートで計算
- 手数料マスタ、送料マスタ、判定基準マスタ管理
- 送料・手数料・広告費・返品未着バッファ込みの利益計算
- リスクチェックによるA/B/C/D判定
- 候補一覧、並び替え、絞り込み
- ChatGPT精査用プロンプト生成

## 使っている外部API

為替だけ自動取得します。無料・APIキー不要のFrankfurter APIを使います。

- 公式ドキュメント: https://frankfurter.dev/
- 使用エンドポイント: `https://api.frankfurter.dev/v2/rates`

商品ページ、eBay Sold、Amazon、Yahooショッピングなどへの自動アクセスやスクレイピングは行いません。

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Supabase設定

Supabaseを使わない場合でも、このPC内の `data/local_app.db` に保存できます。外出先スマホから保存したい場合は、既存SupabaseプロジェクトにeBay専用テーブルを追加してください。

1. Supabaseプロジェクトを開きます。既存プロジェクトでも使えます。
2. SQL Editorで `sql/ebay_preflight_check.sql` を実行し、既存のeBay用テーブルがないことを確認します。
3. SQL Editorで `sql/schema.sql` を実行します。
4. 続けて `sql/seed_master_data.sql` を実行します。
5. 必要なら `sql/sample_product_candidates.sql` を実行します。
6. `.streamlit/secrets.toml.example` を参考に `.streamlit/secrets.toml` を作成します。

```toml
[supabase]
url = "https://your-project.supabase.co"
anon_key = "your-supabase-anon-key"

APP_LOGIN_PASSWORD = "公開デプロイ時だけ設定"
```

`service_role` キーは使わないでください。`.streamlit/secrets.toml` は `.gitignore` 済みなので、GitHubへコミットしないでください。

## SQL

- 事前確認: `sql/ebay_preflight_check.sql`
- テーブル作成: `sql/schema.sql`
- 手数料・送料・判定基準の初期データ: `sql/seed_master_data.sql`
- テスト用商品候補: `sql/sample_product_candidates.sql`

初期データの手数料・送料はサンプルです。実運用前に公式情報で確認し、マスタ管理画面で更新してください。

Supabase上のテーブル名は、既存ツールと混ざらないようにすべて `ebay_` で始まります。BAR原価計算ツール側のテーブルには触りません。

## 画面

- ダッシュボード: 候補数、判定数、最高利益、最高ROI、マスタ警告
- 商品候補登録: スマホ向け1カラム入力、入力中の概算利益表示
- 候補一覧: カード型表示、並び替え、絞り込み
- マスタ管理: 手数料、送料、判定基準
- 為替更新: USD/JPY、AUD/JPYの取得と保存
- ChatGPT精査プロンプト生成: 保存済み候補からコピー用プロンプト作成

## 安全設計

- Supabase URLとanon keyはStreamlit secretsで管理
- 秘密情報のハードコードなし
- 商品URLは文字列保存のみで自動アクセスなし
- 為替以外のマスタは自動更新なし
- 30日以上未確認のマスタは警告
- 送料マスタがない重量帯は利益計算を完了しない
- 高リスク素材・商標・配送リスクは安全側に判定

## 動作確認

```bash
python -m compileall app.py ebay_tool tests
python -m unittest discover -s tests
```

## 注意

無料運用を前提にしていますが、SupabaseやStreamlit Community Cloudなどの無料枠の条件は変わる可能性があります。公開デプロイする場合は、`login_password` を設定して簡易ログインを有効にしてください。
