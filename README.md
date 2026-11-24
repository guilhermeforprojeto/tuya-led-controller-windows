# Controle LED Tuya para Windows — RGB+CCT na bandeja do sistema

Controle fitas LED Wi-Fi Tuya e Smart Life pelo computador Windows: ligar/desligar, escolher cores RGB, ajustar brilho e branco quente/frio. O **Controle LED** usa a Tuya Cloud API e fica na bandeja, perto do relógio.

**English:** A lightweight Windows system tray app to control Tuya / Smart Life Wi-Fi RGB+CCT LED strips using the Tuya Cloud API. [English instructions](README.en.md).

## Comece aqui

1. [Configure o projeto na Tuya](docs/configurar-tuya.md).
2. [Instale e gere o executável](#instalação-no-windows).
3. [Configure a fita no aplicativo](#primeira-abertura).
4. [Escolha como acompanhar a inicialização e o desligamento do PC](#iniciar-com-o-windows-e-desligar-os-leds-com-o-pc).

Projeto independente, sem vínculo oficial com Tuya, ASUS, OpenRGB ou Google. Os LEDs da placa-mãe e das memórias podem ser sincronizados com a fita [via OpenRGB](#leds-da-placa-mãe-e-das-memórias-openrgb).

## Interface

Tema escuro e limpo: poucas superfícies, seções separadas por espaço e título, fonte Segoe UI Variable (Windows 11), cantos contínuos (squircle) e raios concêntricos. A prévia mostra o nome e o brilho da cor; barras de brilho e temperatura aceitam clique, arraste, roda do mouse e setas. O ícone da bandeja, da janela e do executável mostra um LED na cor atual.

**Seletor de cores:** abas **Vivas** (cores puras, as mais fiéis no LED), **Aconchego**, **Foco**, **Pantone** (cores do ano de 2017 a 2026, aproximadas em HEX) e **Livre** (campo de matiz × intensidade e código HEX), com as cores **recentes**. Clique duplo usa a cor na hora. No LED o brilho é ajustado à parte, então tons escuros aparecem mais vivos.

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

## Abas e efeitos

- **Abas de dispositivo:** Geral, Fita, Placa-mãe e Memórias. Cada aba guarda a própria cor, o brilho e o efeito. **Aplicar em Geral** envia a mesma seleção para todos e a copia para as outras abas. Ligar/Desligar valem para a aba aberta, e o menu da bandeja liga/desliga tudo.
- **Modos:** Cor, Branco e Efeitos.
- **Programas que interferem nos LEDs:** só um programa pode controlar os LEDs por vez. Para o Controle LED funcionar corretamente, remova todo e qualquer outro software de RGB. O app procura, a cada minuto, o ASUS Armoury Crate/Aura Sync (serviço `LightingService`, processos `Aac*DramHal`/`Aac*MbHal`, componentes "AURA" instalados e o app da Microsoft Store), Corsair iCUE, SignalRGB, MSI Center/Mystic Light, Gigabyte RGB Fusion, ASRock Polychrome, NZXT CAM, Razer Synapse, XPG, Kingston FURY CTRL, T-Force, Thermaltake, Cooler Master, Lian Li, HyperX, G.Skill, Crucial, Patriot e uma segunda cópia do OpenRGB. Enquanto houver algum, aparecem um aviso fixo na janela, uma notificação na bandeja e o ícone indica o problema. **Resolver** abre o passo a passo de remoção com **Parar agora** (para tudo na hora, com permissão de administrador), **Desinstalar** em cada componente e a dica da BIOS ASUS que reinstala o Armoury Crate sozinho.
- **Painel da bandeja:** clique com o botão direito no ícone perto do relógio para abrir um painel no visual do app: cores, brancos, efeitos, brilho, ligar/desligar, aviso de conflitos e atalhos. Vale para tudo, como a aba Geral. Clique fora ou Esc para fechar; clique simples abre a janela.
- **Rotinas por horário:** em Opções → Rotinas e perfis (ou no painel da bandeja). Escolha horário, dias e ação: aplicar a cor/efeito atual, ligar ou desligar. O PC precisa estar ligado no horário.
- **Perfis por jogo ou app:** escolha um programa aberto na lista (ou digite o .exe) e a cor/efeito. Enquanto ele estiver aberto (ou só em primeiro plano), os LEDs mudam; quando fecha, voltam às cores de antes. O primeiro perfil da lista tem prioridade.
- **Efeitos predefinidos:** Estático, Respirar, Piscar, Arco-íris, Ciclo de cores, Perseguição e Cintilar, com velocidade Lenta, Média ou Rápida. Na fita viram cenas Tuya (`scene_data_v2`); na placa e nas memórias usam os efeitos de hardware do OpenRGB. Respirar, Piscar e Perseguição usam a cor escolhida. Na placa e nas memórias, Arco-íris, Ciclo e Cintilar seguem o brilho do próprio hardware.

## LEDs da placa-mãe e das memórias (OpenRGB)

Com a opção **Sincronizar placa-mãe e memórias (OpenRGB)**, cada **Aplicar**, **Ligar** e **Desligar** também vale para a placa-mãe (inclusive headers ARGB) e para as memórias RGB. Pensado para a ASUS TUF GAMING B550M-PLUS com memórias ADATA/XPG DDR4; a comunicação real com o hardware ainda precisa ser validada.

O SDK Aura do Armoury Crate não lista dispositivos nas versões atuais, por isso a integração usa o [OpenRGB](https://openrgb.org/):

1. No Armoury Crate, desative o controle de iluminação (ou pare o serviço **LightingService**). Os dois programas disputam o mesmo hardware.
2. Instale o OpenRGB 1.0 ou superior e abra-o **como administrador** na primeira vez (as memórias usam o barramento SMBus e exigem o driver PawnIO que o instalador oferece).
3. Confira se a placa e as memórias aparecem. Na aba **SDK Server**, clique em **Start Server** (porta 6742). Em **Settings**, ative iniciar com o Windows, minimizado, com o servidor ligado.
4. No Controle LED, abra **Opções → Configurações**, marque a sincronização e clique em **Testar OpenRGB**.

O brilho é aplicado escurecendo a cor, e o modo Branco vira um tom quente/frio aproximado. Sem credenciais Tuya, o app funciona só com os LEDs do PC. Se a fita ou o OpenRGB falhar, o outro ainda recebe o comando e o rodapé mostra o aviso. A última seleção é lembrada e restaurada no PC ao iniciar com o Windows.

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

## Memórias pente por pente

Na aba **Memórias** aparecem os pentes **1, 2, 3, 4** e **Todos**. Escolha um ou mais e
clique em Aplicar, Ligar ou Desligar: só os pentes marcados mudam, os outros ficam como
estão. Embaixo de cada pente há **Desligar/Ligar**, e **Apagar outros** apaga todos os não marcados.

- **Calibrar ordem:** acende um pente por vez e pergunta em qual encaixe da placa ele está
  (contando a partir do processador); no fim dá para conferir com **Piscar**, ajustar com as
  setas e salvar. Também dá para fazer à mão: o botão **Piscar** acende um pente de branco para você ver
  qual é qual, e as setas trocam a posição. Os efeitos andam do pente 1 para o último.
- Os efeitos das memórias são calculados pelo próprio app (cerca de 30 quadros por
  segundo), por isso ficam em ordem e sincronizados. A prévia da janela mostra o
  mesmo efeito, no mesmo ritmo; o ícone da barra fica fixo, na cor escolhida.
- O app precisa ficar aberto (pode ser só na bandeja) para os efeitos animados das
  memórias continuarem. O estado de cada pente é salvo e volta ao abrir o app.

## Cores puras e "Branco na cor"

O LED não funciona como o monitor: um canal em 10% quase não aparece na tela, mas no
LED acende 10% de verdade e mistura branco na cor (o vermelho fica "opaco"). Por isso o
app corrige cada cor antes de enviar (fita, placa-mãe e memórias): a cor chega pura e o
brilho não muda. O modo **Branco** não passa por essa correção.

Para clarear de propósito, use **Branco na cor** (abaixo das cores): 0% é a cor pura e
quanto mais alto, mais branca. Vale também para os efeitos.

## O que muda na hora e o que espera o clique

- **Placa-mãe e memórias** (OpenRGB, no próprio PC): mudam assim que você escolhe a cor,
  o efeito, o brilho ou o branco. Nas abas Placa-mãe e Memórias não há botão Aplicar.
- **Fita** (nuvem Tuya): só muda ao clicar em **Aplicar na fita**, para não mandar um
  comando pela internet a cada toque. Na aba Geral, o botão envia a seleção para a fita.
