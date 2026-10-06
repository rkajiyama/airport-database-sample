# Airport Database Sample

実在の空港・航空会社マスターと、合成した便・予約を組み合わせたMySQL向けサンプルDBです。
データは **CC BY 4.0**、生成プログラム・独自DDL・説明文書は **MIT** です。
元のOurAirportsはPublic Domain、Wikidataの構造化データはCC0です。
詳細は [LICENSE](LICENSE) と [SOURCES.md](SOURCES.md) を参照してください。

## 収録内容

2026年10月6日取得のスナップショットを同梱しています。

| テーブル | 件数 | 内容 |
|---|---:|---|
| country | 249 | OurAirportsの全件 |
| region | 3,987 | OurAirportsの全件 |
| airport | 86,208 | OurAirportsの空港全件 |
| airline | 6,198 | Wikidataの定義した抽出条件に合う全件 |
| aircraft_type | 1 | 合成機材種別 |
| aircraft | 167 | 合成機体 |
| route | 322 | 合成路線 |
| flight_schedule | 334 | 合成時刻表 |
| flight | 10,000 | 合成した日付別便 |
| passenger | 30,000 | 合成乗客 |
| booking | 100,000 | 合成予約 |

全件マスターのうち30空港・10社を運航生成に使います。路線・便番号・運航時刻・価格・遅延などは
実際の運航を表しません。航空会社の網羅範囲はWikidataの分類に依存します。
IATA/ICAOコードがない施設や廃業会社も保持します。

## 利用方法

Python 3.11以上とシステムのIANAタイムゾーンデータ、MySQL 8.4を使用します。
同梱データの利用・再生成にはネットワークも追加Pythonライブラリも不要です。

```sh
# 同梱の取得元スナップショットからCSVと投入用SQLを生成
PYTHONPATH=src python3 -m airport_sample.generate

# 全件収録、参照、運航・座席・時刻の整合性を確認
PYTHONPATH=src python3 -m airport_sample.validate

# 新規の空のDBに投入。ホスト・ユーザーは自分の環境に合わせて変更
mysql --default-character-set=utf8mb4 -h localhost -u USER -p < sql/schema.sql
mysql --binary-mode --default-character-set=utf8mb4 -h localhost -u USER -p < data/small/load.sql
mysql --default-character-set=utf8mb4 -h localhost -u USER -p < sql/examples.sql
```

`schema.sql`は既存テーブルを削除しません。同名のテーブルがある場合はエラーとなるので、新規の空の
`airport_sample`スキーマを使ってください。`load.sql`は生成物で、Gitには同梱していません。
CSVと元データは同梱しています。

## 再生成と拡張

`config/small.json`の乱数シード、期間、便数、乗客数、1便あたり予約数、運航対象を変更します。
便数は往復生成のため偶数、1便あたり予約は最大180件です。全件マスターは縮小されません。

```sh
PYTHONPATH=src python3 -m airport_sample.generate --config config/small.json --output data/regenerated
PYTHONPATH=src python3 -m airport_sample.validate --output data/regenerated
python3 -m unittest discover -s tests -v
```

固定した元データ・設定・Python/タイムゾーン環境で再現できます。実装は全行をメモリに保持するので、
数千万予約への拡張にはストリーミング出力・分割投入の追加が必要です。

取得元を更新するときだけ、次を実行します。既存スナップショットを置換するため、変更をレビューして
件数・出典・生成データを更新してください。航空会社はAPIの取得時点の結果であり、更新の途中で
OurAirportsとWikidataが同一時刻になる保証はありません。

```sh
PYTHONPATH=src python3 -m airport_sample.fetch
PYTHONPATH=src python3 -m airport_sample.generate
PYTHONPATH=src python3 -m airport_sample.validate
```

## 時刻と運航モデル

運航曜日・有効期間・出発時刻はUTC基準です。現地時刻は便ごとにタイムゾーンから変換します。
現地の毎日同じ時刻を保証するモデルではありません。機体は1日1往復し、出発基地へ戻ります。
予定折返し時間は60分です。往復は同じ遅延・欠航状態を使い、実績の機体連続性も維持します。
時差・日付変更・夏時間を考慮し、UTC日時はMySQLの`DATETIME`に格納します。
運航対象外の空港のタイムゾーンはNULLです。

## 帰属表示の例

> Airport Database Sample — RKajiyama.
> https://github.com/rkajiyama/airport-database-sample
> Dataset compilation and synthetic records: CC BY 4.0.
> Airport data: OurAirports (Public Domain); airline data: Wikidata (CC0).
> Changes: [利用者が行った変更を記載].

このプロジェクトのCC BY条件は独自のデータ・編集部分に適用し、元のPublic Domain/CC0データに
新たな制約を付けません。航空会社・空港の名称を使っても、各社による承認や提携を意味しません。

データ辞書は [docs/data-dictionary.md](docs/data-dictionary.md)、検証はGitHub Actionsの
PythonテストとMySQL 8.4投入テストで実行します。
