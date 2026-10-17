# Controle LED Tuya para Windows — RGB+CCT na bandeja do sistema

Controle fitas LED Wi-Fi Tuya e Smart Life pelo computador Windows: ligar/desligar, escolher cores RGB, ajustar brilho e branco quente/frio. O **Controle LED** usa a Tuya Cloud API e fica na bandeja, perto do relógio.

**English:** A lightweight Windows system tray app to control Tuya / Smart Life Wi-Fi RGB+CCT LED strips using the Tuya Cloud API. [English instructions](README.en.md).

## Comece aqui

1. [Configure o projeto na Tuya](docs/configurar-tuya.md).
2. [Instale e gere o executável](#instalação-no-windows).
3. [Configure a fita no aplicativo](#primeira-abertura).
4. [Escolha como acompanhar a inicialização e o desligamento do PC](#iniciar-com-o-windows-e-desligar-os-leds-com-o-pc).

Projeto independente, sem vínculo oficial com Tuya, ASUS ou Google. A integração com Armoury Crate / Aura Sync **não está implementada**.

## Interface

Tema escuro, prévia da seleção, paleta de cores, barra de brilho com preenchimento lilás e puxador circular e botão de aplicar destacado. O rodapé inclui o crédito clicável da System Bee Solutions. A tela principal concentra os ajustes de iluminação. **Arquivo** reúne minimizar para a bandeja e sair; **Opções** reúne configurações e atualização do estado. A prévia é ilustrativa; a aparência física depende da fita.

## Recursos

- Ligar e desligar sem trocar a cor atual.
- Escolher cores RGB e ajustar brilho.
- Ajustar branco quente/frio em fitas e controladores RGBCCT compatíveis.
- Manter o aplicativo na bandeja ao fechar a janela.
- Iniciar automaticamente após entrar na conta do Windows.
- Opcionalmente ligar os LEDs na inicialização automática.
- Opcionalmente tentar desligar os LEDs ao desligar ou reiniciar o PC.
- Consultar o estado da fita sob demanda, sem consultas contínuas.

## Compatibilidade e requisitos

| Item | Requisito |
| --- | --- |
| Sistema | Windows 10/11; a integração nativa ainda precisa de validação em diferentes PCs |
| Dispositivo | Controlador Wi-Fi Tuya / Smart Life com comandos padrão RGB+CCT compatíveis |
| Região desta versão | **Western America Data Center**, endpoint `openapi.tuyaus.com` |
| Rede | Acesso à internet no PC e no controlador |
| Tuya | Projeto com acesso válido à API, dispositivo vinculado e permissão de controle |
| Para gerar o EXE | Python 3.11 ou superior, com Python Launcher e Tcl/Tk |

Um dispositivo aparecer no Google Home não concede automaticamente acesso à API da Tuya. Esta versão não faz controle Bluetooth direto nem controle local pela rede. Outros data centers exigem adaptar `ENDPOINT` no código conforme a [documentação de endpoints da Tuya](https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4).

## Instalação no Windows

1. [Baixe o Python para Windows](https://www.python.org/downloads/windows/). Inclua **Python Launcher** e **Tcl/Tk** na instalação.
2. Baixe o código deste repositório em **Code → Download ZIP** e extraia tudo.
3. Abra a pasta extraída e execute **Gerar_executavel.bat**.
4. Aguarde a instalação das dependências e a geração do programa.
5. Abra **dist → ControleLED.exe**.

O script precisa de internet na primeira montagem. Depois de gerado, o executável pode ser usado sem instalar Python na máquina de destino. O binário é gerado localmente; este pacote de código não inclui um EXE pré-compilado.

Para desenvolver, em PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe controle_led.py
```

Também há um workflow em **Actions → Build Windows** que gera o EXE como artefato de uma execução bem-sucedida. A geração não substitui o teste com um controlador real.

## Primeira abertura

Em **Opções → Configurações**, preencha:

| Campo | Onde encontrar |
| --- | --- |
| Access ID / Client ID | Overview do projeto Tuya vinculado à fita |
| Access Secret | Overview do mesmo projeto |
| Device ID | Devices → All Devices → linha do controlador |

Clique em **Salvar e testar conexão**. Depois:

1. Clique em **Ligar**.
2. Escolha **Cor RGB** ou **Branco**.
3. Ajuste cor, brilho e, no modo branco, temperatura.
4. Clique no botão destacado **Aplicar cor e brilho** (ou **Aplicar branco e brilho**).

**Aplicar** também liga a fita. O menu **Opções → Atualizar estado da fita** somente consulta; **Ligar/Desligar** preserva o modo e a cor. O ajuste de temperatura precisa dos canais de branco da fita, não apenas de um controlador anunciado como RGBCCT.

## Iniciar com o Windows e desligar os LEDs com o PC

Em **Opções → Configurações**, as opções são independentes:

| Opção | Comportamento |
| --- | --- |
| Iniciar aplicativo com o Windows | Inicia na bandeja após o login do usuário |
| Ligar LEDs ao iniciar com o Windows | Envia somente ligar; desmarcado, não altera a fita |
| Desligar LEDs ao desligar/reiniciar o PC | Tenta enviar desligar quando o Windows confirma o encerramento |

Mantenha o EXE numa pasta fixa antes de salvar. Se mover o arquivo, abra-o novamente e salve a configuração para atualizar o caminho. Se criou um atalho manual em `shell:startup`, remova esse atalho para evitar duas formas de inicialização.

Fechar a janela mantém o aplicativo ativo. **Sair**, no menu da bandeja, encerra o programa e a integração. Bloquear a sessão, sair da conta, suspender e hibernar não acionam o desligamento dos LEDs nesta versão.

A tentativa de desligar tem um limite de aproximadamente três segundos e depende da rede, da nuvem Tuya e do aplicativo em execução. Não é garantida em desligamento forçado, queda de energia ou indisponibilidade de rede. Na inicialização automática, há até seis tentativas de ligar para lidar com rede ainda indisponível.

## Configuração e privacidade

As credenciais ficam em `%APPDATA%\ControleLED\config.json`, em texto local. Os registros de inicialização e encerramento ficam em `%APPDATA%\ControleLED\eventos.log`.

Não publique credenciais, tokens, seu arquivo `config.json` ou prints que mostrem o Secret. O código público não inclui Device ID pessoal nem chaves de acesso. As requisições são enviadas por HTTPS à Tuya.

## Problemas comuns

| Sintoma | O que conferir |
| --- | --- |
| Data center não selecionado | Adicione o data center correto ao projeto e selecione-o na página |
| Dispositivo não aparece | Região da conta e projeto; vinculação por QR Code no aplicativo correto |
| Dispositivo só permite leitura | Em All Devices, altere a permissão para controlável; confira a cota |
| Erro de assinatura / 1004 | Access ID e Secret do mesmo projeto, sem espaços; relógio do Windows correto |
| Sem permissão / 1106 | Serviços autorizados, região e permissão de controle do dispositivo |
| Falha após um período funcionando | Validade, cotas e condições do serviço IoT Core no painel Tuya |
| Não inicia com o Windows | Caminho do EXE, opção salva e bloqueios nas configurações de inicialização do Windows |
| LEDs não desligam com o PC | App aberto, opção marcada, internet disponível e registro em `eventos.log` |
| App já aberto | Procure o ícone na área de ícones ocultos, perto do relógio |

## Comandos Tuya utilizados

| Função | Comando |
| --- | --- |
| Ligar/desligar | `switch_led` |
| Modo branco/RGB | `work_mode` (`white` / `colour`) |
| Brilho branco | `bright_value_v2` (10–1000) |
| Temperatura | `temp_value_v2` (0–1000) |
| Cor RGB | `colour_data_v2` (`h`, `s`, `v`) |

A compatibilidade depende do mapeamento de comandos do produto. Não há promessa de suporte a todos os dispositivos Tuya. O acesso à API depende das condições e da validade do plano da Tuya; o aplicativo não garante gratuidade desse serviço.

## Validação

Os testes automatizados usam simulações para assinatura, comandos, token, inicialização e eventos de encerramento. Não acessam a conta Tuya nem uma fita real. O controle pelo painel Tuya foi testado durante o desenvolvimento; o executável, os eventos nativos e a comunicação real do aplicativo ainda precisam de validação no Windows.

```powershell
py -3 -m unittest discover -s tests -v
```

## Links oficiais

- [Tuya Developer Platform](https://platform.tuya.com/)
- [Tuya: criar e configurar projeto Smart Home](https://developer.tuya.com/en/docs/iot/smart-home-quick-start?id=Kbvwrxn6mngbd)
- [Tuya: vincular dispositivos](https://developer.tuya.com/en/docs/iot/link-devices?id=Ka471nu1sfmkl)
- [Tuya: endpoints e estrutura de requisição](https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4)
- [Tuya: assinatura da API](https://developer.tuya.com/en/docs/iot/new-singnature?id=Kbw0q34cs2e5g)
- [Tuya: controle de dispositivos com Python](https://developer.tuya.com/en/docs/iot/device-control-best-practice-python?id=Kav4zc0nphsn5)

Desenvolvido por **Guilherme Santana Santos**. [System Bee Solutions](https://systembee.com.br/).
