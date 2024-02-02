[![CI](https://github.com/qmonus/net-faker/actions/workflows/ci.yml/badge.svg)](https://github.com/qmonus/net-faker/actions/workflows/ci.yml)

# Qmonus-NetFaker
Qmonus-NetFakerは、擬似ネットワーク装置を開発するためのPythonベースのフレームワークです。Qmonus-SDKによるネットワーク装置制御の試験にご利用いただけます。

## 機能
サポートしているプロトコルは以下の通りです。
- netconf 1.0
- http
- https
- ssh
- telnet
- snmp

netconfについては、YANGファイルによりネットワーク装置のコンフィグモデルを定義できます。ただし、typeやnamespaceのチェックは行いません。本格的な試験を行う場合は実機をご利用ください。

## インストール
Python 10で動作します。

```sh
pip install git+https://github.com/qmonus/net-faker.git@${VERSION}
```

## アプリケーション構成
`manager`と`stub`の二種類を起動する必要があります。

- `manager`
  - Qmonus-NetFaker管理用の[REST-API](#rest-api)を提供します。
  - [Plugin](#plugin)に従い、`stub`から転送されてくる命令を実行します。
    - 各NW装置のコンフィグの管理は`manager`で行います。
  - `manager`は1つ起動する必要があります。
- `stub`
  - netconfやsshなどの接続を受け付けます。
    - 裏で`manager`とHTTP通信します。実際のnetconfやsshに対する処理は`manager`側で行います。
  - 擬似したいネットワーク装置の台数分`stub`を起動する必要があります。

## 利用方法
### 開発の流れ
以下のようになります。
1. `initコマンド`で`project`を作成
2. Pluginを開発
3. `runコマンド`で`manager`や`stub`を起動

参考情報
- [コマンドの詳細](#cli)
- [Pluginの詳細](#plugin)

### 実行例
`initコマンド`で`project`を作成します。
```sh
mkdir netfaker
cd netfaker
python -m qmonus_net_faker init .
```

雛形のpluginが生成されますので、それをもとにPluginを開発します。[詳細はこちら](#plugin)です。

Pluginを作成したら、`manager`と`stub`を起動します。`stub`は擬似したいネットワーク装置の数だけ起動する必要があります。

```sh
# manager起動
python -m qmonus_net_faker run manager .

※この例ではproject_pathとしてカレントディレクトリ"."を指定しています。
※managerはデフォルトでは0.0.0.0:10080でhttp接続を待ち受けます。
```

```sh
# stub起動
python -m qmonus_net_faker run stub netfaker-stub-0 http://127.0.0.1:10080

※この例ではstub_idとして"netfaker-stub-0"、managerのendpointとして"http://127.0.0.1:10080"を指定しています。
※stub_idは、起動するstub毎に異なる値を設定してください。
※stubはデフォルトでは0.0.0.0:20022でssh/netconf接続、0.0.0.0:20080でhttp接続、0.0.0.0:20443でhttps接続、0.0.0.0:161でsnmp接続、0.0.0.0:20023でtelnet接続を待ち受けます。
```

## Plugin
httpやnetconf、ssh等のリクエストに対する処理を定義します。stubs、yangs、moduleの3種類を用意する必要があります。

### ディレクトリ構造
```
{project_path}/
+-- stubs/
│   +-- stubs.yaml
+-- yangs/
│   +-- {yang_name_1}/
│   │   +-- {yang_file_1}.yang
│   │   +-- {yang_file_2}.yang
│   │   ...
│   .   +-- {yang_file_x}.yang
│   +-- {yang_name_x}/
│       +-- {yang_file_1}.yang
│       +-- {yang_file_2}.yang
│       .
│       +-- {yang_file_x}.yang
+-- module/
    +-- __init__.py
    +-- handlers/
       +-- __init__.py
       +-- {handler_name_1}/
       │  +-- __init__.py
       │  +-- {python_script_1}.py
       │  .
       │  +-- {python_script_x}.py
       +-- {handler_name_x}/
          +-- __init__.py
          +-- {python_script_1}.py
          .
          +-- {python_script_x}.py
```

### stubs
`stubs.yaml`に、`stub_id`ごとの設定を定義してください。

```yaml
stubs:
  - id: netfaker-stub-0    # Required: stub_idを指定
    description: junos-0   # Optional: descriptionを指定 (default: '')
    handler: junos         # Required: handler_nameを指定
    yang: junos            # Optional: yang_nameを指定 (default: '')
    enabled: true          # Optional: アクセス可否を指定 (default: true)
  - id: netfaker-stub-1
    description: junos-1
    handler: junos
    yang: junos
    enabled: true
```

### yangs
`{project_path}/yangs`配下に任意の名前のディレクトリ`{yang_name}`を作成し、その配下に`YANG file`を作成します。`YANG file`の拡張子は`.yang`にしてください。尚、Qmonus-NetFakerはlistやcontainer、leafなどのコンフィグの階層構造は認識しますが、厳密なtypeやnamespaceのチェックは行いません。

`YANG file`を用意したら、`buildコマンド`を実行して`yang_tree`を生成します。
```sh
python -m qmonus_net_faker build {project_path} {yang_name}
```

`{project_path}/yangs/{yang_name}`配下に`yang_tree`ディレクトリが生成され、さらにその配下にファイルが生成されます。

### module
pythonのmoduleです。`{project_path}/handlers`配下に任意の名前のディレクトリ`{handler_name}`を作成し、その配下に`__init__.py`ファイルを作成してください。`__init__.py`には以下の内容を含めてください。`init コマンド`により生成される雛形も参考にしてください。
- `handler class`を定義し、httpやnetconfのリクエストに対する処理を記述
- `setup()`を定義し、上記の`handler class`をインスタンス化して返却

## CLI
`init`
```sh
python -m qmonus_net_faker init [options] {project_path}

positional arguments:
  project_path  project directory path

optional arguments:
  -h, --help   show this help message and exit
```

`build`
```sh
python -m qmonus_net_faker build [options] {project_path} {yang_name}

positional arguments:
  project_path          project directory path
  yang_name             YANG module name

optional arguments:
  -h, --help            show this help message and exit
  --log-level {debug,info}
                        log level
```

`run manager`
```sh
python -m qmonus_net_faker run manager [options] {project_path}

positional arguments:
  project_path          project directory path

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           host to listen on (default: 0.0.0.0)
  --port PORT           port to listen on (default: 10080)
  --log-level {debug,info}
                        log level (default: info)
  --log-file-path LOG_FILE_PATH
                        absolute path for log file (default: None)
  --log-file-size LOG_FILE_SIZE
                        max log file size (default: 3145728)
  --log-file-backup-count LOG_FILE_BACKUP_COUNT
                        log file backup count (default: 2)
```

`run stub`
```sh
python -m qmonus_net_faker run stub [options] {stub_id} {manager_endpoint}

positional arguments:
  stub_id               stub-id
  manager_endpoint      manager endpoint: http://{manager_host}:{manager_port}

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           host to listen on (default: 0.0.0.0)
  --http-port HTTP_PORT
                        port to listen on (default: 20080)
  --https-port HTTPS_PORT
                        port to listen on (default: 20443)
  --ssh-port SSH_PORT   port to listen on (default: 20022)
  --telnet-port TELNET_PORT
                        port to listen on (default: 20023)
  --snmp-port SNMP_PORT
                        port to listen on (default: 20161)
  --protocol {ssh,http,https,telnet,snmp} [{ssh,http,https,telnet,snmp} ...]
                        protocol (default: ['ssh', 'http', 'https', 'telnet', 'snmp'])
  --log-level {debug,info}
                        log level (default: info)
  --log-file-path LOG_FILE_PATH
                        absolute path for log file (default: None)
  --log-file-size LOG_FILE_SIZE
                        max log file size (default: 3145728)
  --log-file-backup-count LOG_FILE_BACKUP_COUNT
                        log file backup count (default: 2)
```

## REST-API
- [openapi.yaml](docs/openapi.yaml)
