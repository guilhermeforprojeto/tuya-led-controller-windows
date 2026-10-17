# Publicar o Controle LED no GitHub

## Nome e descrição

Nome sugerido: **tuya-led-controller-windows**

Descrição para o campo About:

> Windows tray app for Tuya / Smart Life RGB+CCT LED strips. Controle fitas LED Wi-Fi pelo PC: cores, brilho, inicialização e desligamento.

Topics sugeridos (GitHub → About → engrenagem):

```text
tuya smartlife windows led-controller rgb rgbcct system-tray python tkinter home-automation iot tuya-api
```

O nome, a descrição e o README explicam a mesma finalidade, com termos usados por quem procura essa solução. A documentação em inglês amplia a compreensão por outros públicos. Não há garantia de posição no Google ou no GitHub.

## Enviar sem terminal

1. Entre na sua conta do [GitHub](https://github.com/).
2. Abra [New repository](https://github.com/new).
3. Use o nome sugerido e a descrição acima. Escolha **Public** para descoberta pública.
4. Crie o repositório vazio.
5. Em **Add file → Upload files**, envie os arquivos e pastas do projeto preservando a estrutura.
6. Confira a presença de `.github/workflows/build-windows.yml` e `.gitignore`. Se o navegador não mostrar arquivos ocultos, use Git para enviar tudo.
7. Adicione os topics no campo About.
8. Em **Actions**, execute **Build Windows**, confira o resultado e baixe o artefato.
9. Teste o EXE no Windows. Só depois, se quiser distribuir o binário, crie uma Release e anexe o EXE validado com notas da versão.

## Enviar com Git

Execute dentro da pasta extraída. Substitua SEU-USUARIO pela conta de destino:

```powershell
git init
git add .
git diff --cached --stat
git commit -m "Initial release: Tuya LED controller for Windows"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/tuya-led-controller-windows.git
git push -u origin main
```

Antes do commit, confira que nenhum arquivo pessoal, Secret, token ou `config.json` foi incluído. A versão preparada deixa o Device ID vazio para cada pessoa informar o seu.

## Descoberta e manutenção

- Use títulos claros nas Releases e descreva mudanças reais.
- Quando houver uma Release, adicione o link real dela no início do README.
- Acrescente uma captura real do programa sem credenciais após validar a interface.
- Compartilhe o link do repositório numa publicação útil em seu site ou perfil profissional.
- Responda dúvidas e mantenha instalação, limitações e compatibilidade atualizadas.
- Evite repetir palavras-chave sem contexto ou anunciar funções ainda não implementadas.

Não foi escolhida uma licença de distribuição nesta preparação. Antes de divulgar como open source, decida quais permissões quer conceder e acrescente a licença correspondente. Um repositório público sem licença não concede automaticamente uma licença ampla de uso e redistribuição.

Referências: [README](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes), [Topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics), [Licenciamento](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
