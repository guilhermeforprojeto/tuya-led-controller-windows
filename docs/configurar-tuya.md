# Como configurar a API Tuya para controlar uma fita LED no Windows

## 1. Prepare o dispositivo

Cadastre seu controlador Wi-Fi no Tuya Smart ou Smart Life e confirme que consegue controlá-lo no celular pela internet. Mantenha o dispositivo online.

## 2. Crie o projeto

Acesse a [Tuya Developer Platform](https://platform.tuya.com/). Em **Cloud → Project Management** (em outras versões, **Cloud → Development**), crie um projeto **Smart Home**.

Selecione um data center que atenda à região da conta do aplicativo. Este programa está configurado para **Western America Data Center**. Não escolha essa região apenas por usar o programa: se sua conta estiver em outro centro, adapte o endpoint no código conforme a [lista oficial](https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4).

## 3. Confira serviços e cotas

Na aba **Service API**, confira o acesso aos serviços de controle e autenticação. Na configuração usada neste projeto, **IoT Core** e **Authorization Token Management** estavam autorizados, além dos serviços básicos do projeto.

Confira também validade, cotas e eventual custo na plataforma. Autorizar um serviço não assegura acesso gratuito permanente.

## 4. Vincule a conta do celular

Abra **Devices → Link App Account / Link Tuya App Account → Add App Account**. Escaneie o QR Code com o aplicativo onde a fita está cadastrada e autorize a vinculação. Confira o dispositivo em **All Devices**.

Se aparecer uma mensagem de data center sem acesso, volte a **Overview → Edit**, configure o data center e confira o seletor de região da página.

## 5. Autorize controle e teste

Se a permissão estiver apenas como **Read**, clique em **Change** e converta o dispositivo para controlável. Essa conversão consome uma vaga da cota de dispositivos controláveis.

Em **Debug Device → Device Debugging**, verifique a existência dos comandos `switch_led`, `work_mode`, `bright_value_v2`, `temp_value_v2` e `colour_data_v2`. Teste o liga/desliga. O painel pode enviar também outros campos: confira os valores antes de enviar.

## 6. Preencha o programa

Copie o **Device ID** da lista. Em **Overview**, encontre **Access ID** e **Access Secret**. Use os três campos em **Configuração** no Controle LED e clique em **Salvar e testar conexão**.

Se recriar o projeto, use as chaves novas. Não compartilhe o Secret em issues ou prints.

[Voltar às instruções do aplicativo](../README.md)
