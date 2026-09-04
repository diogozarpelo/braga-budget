# Braga Budget

Sistema de orçamentos desenvolvido para agilizar, organizar e padronizar a criação de propostas comerciais para serviços de vidraçaria.

O projeto nasceu de uma necessidade real de operação da **Vidraçaria Braga** e foi desenvolvido por **Diogo Zarpelão**, reunindo regras de negócio, automação de cálculos, gestão de clientes e geração de propostas comerciais em uma única aplicação.

> **Status:** v1.0 funcional — aplicação local para Windows

---

## 📌 Sobre o projeto

O **Braga Budget** foi criado para substituir processos manuais de cálculo e montagem de orçamentos por um fluxo mais rápido, consistente e confiável.

A aplicação permite cadastrar clientes, montar orçamentos com múltiplos serviços, calcular automaticamente materiais e mão de obra, realizar ajustes comerciais e gerar propostas prontas para envio em **PDF ou PNG**.

A versão 1.0 funciona localmente em Windows e utiliza um banco de dados SQLite persistente.

---

## ✨ Principais funcionalidades

- Cadastro e gerenciamento de clientes
- Ativação e inativação de clientes
- Cadastro e gerenciamento de componentes
- Criação de orçamentos em rascunho
- Múltiplos itens por orçamento
- Diferentes tipos de serviços de vidraçaria
- Cálculo automático da área do vidro
- Cálculo individual de materiais por item
- Componentes e acessórios por item
- Mão de obra automática individual
- Ajuste manual da mão de obra
- Adicional de dificuldade
- Aplicação de desconto
- Ajuste manual do valor final
- Distribuição proporcional do valor comercial entre os itens
- Numeração automática dos orçamentos
- Controle de validade
- Controle de prazo de execução
- Formas e condições de pagamento
- Observações comerciais
- Garantia
- Emissão de orçamento
- Controle de status
- Proteção contra alterações após emissão
- Exportação em PDF
- Exportação em PNG
- Executável para Windows
- Instalador próprio para Windows
- Banco de dados persistente separado da instalação

---

## 🔄 Fluxo principal

```text
Cliente
   ↓
Novo orçamento
   ↓
Itens / serviços
   ↓
Vidro + componentes
   ↓
Mão de obra por item
   ↓
Ajustes comerciais
   ↓
Valor final
   ↓
Emissão
   ↓
PDF / PNG
```

---

## 🧮 Regras de negócio

### Cálculo da área

As medidas são informadas em milímetros e convertidas automaticamente para metros quadrados.

```text
Área = largura × altura / 1.000.000
```

O cálculo considera também a quantidade de unidades do item.

---

### Materiais

Cada item pode possuir componentes próprios, como kits de instalação, roldanas, puxadores, fechaduras e outros materiais necessários ao serviço.

Os componentes são cadastrados separadamente e utilizados durante a composição do orçamento.

---

### Mão de obra por item

Cada item do orçamento possui sua própria mão de obra.

O valor automático corresponde a:

```text
Mão de obra = 50% do valor do vidro + componentes do item
```

O sistema também permite substituir esse valor por uma mão de obra definida manualmente.

---

### Ajuste comercial do valor final

O orçamento possui um valor calculado internamente, mas o usuário pode definir um valor comercial final.

Quando isso acontece, o Braga Budget distribui a diferença proporcionalmente entre os itens do orçamento.

A distribuição utiliza o peso original de cada item e garante que:

```text
Soma dos valores comerciais dos itens = valor final do orçamento
```

Diferenças provocadas por arredondamento são resolvidas automaticamente.

Dessa forma, a proposta apresentada ao cliente mantém valores coerentes sem expor a composição interna de custos.

---

## 📄 PDF comercial

O Braga Budget gera uma proposta comercial pronta para apresentação ao cliente.

O documento contém:

- identidade visual da empresa
- número do orçamento
- dados do cliente
- validade
- prazo de execução
- forma de pagamento
- serviços contratados
- descrição técnica
- valor comercial individual dos serviços
- valor total da proposta
- garantia

Informações utilizadas internamente para formação do preço não são discriminadas no documento comercial.

Isso inclui:

- custo individual dos componentes
- subtotal do vidro
- mão de obra interna
- adicional de dificuldade
- desconto
- ajustes e arredondamentos

---

## 🖼️ Exportação em imagem

Além do PDF, o orçamento pode ser exportado em **PNG**.

A imagem é produzida a partir do próprio documento comercial, mantendo o mesmo conteúdo e identidade visual.

Essa opção facilita o compartilhamento direto por aplicativos de mensagens.

---

## 🛠️ Tecnologias utilizadas

### Backend

- Python
- Flask 3
- SQLite

### Frontend

- HTML5
- CSS3
- JavaScript
- Jinja2

### Geração de documentos

- ReportLab
- PyMuPDF
- Pillow

### Distribuição para Windows

- PyInstaller
- Inno Setup

### Versionamento

- Git
- GitHub

---

## 📁 Estrutura do projeto

```text
braga-budget/
│
├── app/
│   ├── static/
│   │   ├── css/
│   │   ├── icons/
│   │   ├── images/
│   │   └── js/
│   │
│   ├── templates/
│   │
│   ├── __init__.py
│   ├── db.py
│   ├── routes.py
│   └── schema.sql
│
├── docs/
├── tests/
├── BragaBudget.iss
├── requirements.txt
├── run.py
└── README.md
```

---

## 💾 Banco de dados

A versão 1.0 utiliza **SQLite**.

### Ambiente de desenvolvimento

```text
instance/braga_budget.sqlite
```

### Aplicação instalada no Windows

```text
%LOCALAPPDATA%\BragaBudget\braga_budget.sqlite
```

O banco de dados da versão instalada fica separado dos arquivos do programa.

Essa arquitetura permite preservar os dados durante atualizações ou reinstalações da aplicação.

---

## 🚀 Executando o projeto em desenvolvimento

### 1. Clone o repositório

```bash
git clone https://github.com/diogozarpelo/braga-budget.git
cd braga-budget
```

### 2. Crie um ambiente virtual

```bash
python -m venv .venv
```

### 3. Ative o ambiente virtual

No PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### 5. Execute a aplicação

```bash
python run.py
```

O sistema será iniciado localmente em:

```text
http://127.0.0.1:5000
```

O navegador padrão é aberto automaticamente.

---

## 📦 Distribuição para Windows

A aplicação pode ser empacotada como executável utilizando **PyInstaller**.

A distribuição final é preparada através do **Inno Setup**, permitindo instalação tradicional no Windows.

O banco de dados do usuário não fica armazenado dentro da pasta do programa.

---

## Roadmap

O desenvolvimento do Braga Budget está organizado em etapas progressivas. A prioridade é estabilizar cada fase antes de avançar para a próxima, mantendo o projeto utilizável durante toda a evolução.

### Etapa 1 - v1.0 local

Primeira versão funcional preparada para uso real em ambiente Windows.

- [x] Gestão de clientes
- [x] Gestão de componentes
- [x] Criação de orçamentos
- [x] Múltiplos serviços por orçamento
- [x] Cálculo automático de vidro
- [x] Componentes por item
- [x] Mão de obra individual
- [x] Ajustes comerciais
- [x] Distribuição proporcional do valor final
- [x] Emissão de orçamento
- [x] Controle de status
- [x] PDF comercial
- [x] Exportação PNG
- [x] Banco SQLite persistente
- [x] Executável Windows
- [x] Instalador Windows

### Etapa 2 - Validação em uso real

Após a entrega da v1.0, a aplicação entra em um período de utilização real antes das mudanças estruturais.

- [ ] Utilizar o sistema no fluxo real de trabalho
- [ ] Registrar bugs encontrados
- [ ] Identificar dificuldades de usabilidade
- [ ] Coletar sugestões de melhoria
- [ ] Validar cálculos com orçamentos reais
- [ ] Validar emissão, PDF e PNG
- [ ] Organizar e priorizar o feedback recebido

**Janela inicial prevista:** aproximadamente 1 semana de uso real, ajustável conforme o volume de utilização.

### Etapa 3 - Estabilização da v1.0

- [ ] Corrigir bugs identificados
- [ ] Refinar pontos de UX
- [ ] Revisar validações
- [ ] Revisar mensagens de erro
- [ ] Validar persistência dos dados
- [ ] Validar novamente PDF e PNG
- [ ] Criar versão estável
- [ ] Criar tag/release `v1.0.0` no GitHub

### Etapa 4 - Testes automatizados

Ampliar a segurança das futuras mudanças por meio de testes automatizados.

- [ ] Testar cálculos de vidro
- [ ] Testar componentes
- [ ] Testar mão de obra
- [ ] Testar adicionais e descontos
- [ ] Testar distribuição proporcional do valor final
- [ ] Testar emissão de orçamento
- [ ] Testar regras de status
- [ ] Criar testes das principais rotas
- [ ] Criar testes de integração com o banco de dados

### Etapa 5 - Preparação para produção

Antes de expor a aplicação à internet:

- [ ] Separar configurações de desenvolvimento e produção
- [ ] Adotar variáveis de ambiente
- [ ] Manter informações sensíveis fora do código
- [ ] Implementar tratamento adequado de erros
- [ ] Implementar logs
- [ ] Revisar validação de entradas
- [ ] Adicionar proteção CSRF
- [ ] Revisar sessões e cookies
- [ ] Definir estratégia de backup
- [ ] Preparar servidor adequado para Flask em produção
- [ ] Realizar revisão geral de segurança

### Etapa 6 - Migração para PostgreSQL

- [ ] Configurar PostgreSQL no ambiente de desenvolvimento
- [ ] Adaptar a camada de acesso aos dados
- [ ] Revisar consultas específicas do SQLite
- [ ] Testar todas as operações utilizando PostgreSQL
- [ ] Criar processo de migração do banco atual
- [ ] Migrar clientes, componentes e orçamentos
- [ ] Validar integridade dos dados após a migração

### Etapa 7 - Infraestrutura em nuvem

- [ ] Escolher o provedor de hospedagem
- [ ] Provisionar PostgreSQL em nuvem
- [ ] Hospedar o backend Flask
- [ ] Configurar variáveis de ambiente
- [ ] Configurar HTTPS
- [ ] Configurar logs de produção
- [ ] Configurar backups
- [ ] Testar acesso externo
- [ ] Validar estabilidade
- [ ] Migrar os dados reais da versão local

### Etapa 8 - Autenticação e controle de acesso

- [ ] Criar estrutura de usuários
- [ ] Implementar armazenamento seguro de senhas
- [ ] Implementar login e logout
- [ ] Proteger rotas autenticadas
- [ ] Implementar controle de sessão
- [ ] Implementar autorização
- [ ] Revisar segurança dos cookies
- [ ] Criar fluxo de alteração de senha

### Etapa 9 - API

- [ ] Definir a arquitetura da API
- [ ] Criar endpoints de clientes
- [ ] Criar endpoints de componentes
- [ ] Criar endpoints de orçamentos
- [ ] Criar endpoints de itens
- [ ] Padronizar respostas JSON
- [ ] Utilizar corretamente códigos HTTP
- [ ] Padronizar respostas de erro
- [ ] Integrar autenticação
- [ ] Definir versionamento da API

Exemplos planejados:

    GET    /api/clients
    POST   /api/clients
    GET    /api/quotes
    POST   /api/quotes
    GET    /api/quotes/{id}
    PUT    /api/quotes/{id}

### Etapa 10 - Documentação da API

- [ ] Documentar endpoints
- [ ] Documentar parâmetros
- [ ] Documentar requests e responses
- [ ] Documentar códigos de erro
- [ ] Documentar autenticação
- [ ] Adotar OpenAPI / Swagger
- [ ] Manter a documentação sincronizada com a implementação

### Etapa 11 - Evolução arquitetural

Objetivos:

- [ ] Separar regras de negócio das rotas
- [ ] Criar camada de serviços
- [ ] Criar camada de acesso a dados
- [ ] Reutilizar regras entre Web e API
- [ ] Reduzir acoplamento
- [ ] Facilitar testes e manutenção

Estrutura planejada:

    app/
    |-- api/
    |-- models/
    |-- repositories/
    |-- routes/
    |-- services/
    |-- static/
    `-- templates/

### Etapa 12 - Braga Budget v2.0 Android

- [ ] Definir arquitetura do aplicativo Android
- [ ] Implementar autenticação
- [ ] Consultar clientes
- [ ] Cadastrar clientes
- [ ] Criar orçamentos
- [ ] Editar orçamentos
- [ ] Consultar histórico
- [ ] Consumir a API central
- [ ] Compartilhar PDF e PNG
- [ ] Sincronizar dados entre Web e Android
- [ ] Tratar indisponibilidade de conexão
- [ ] Preparar distribuição do aplicativo

Arquitetura alvo:

    Web --------+
                |
                +--> Flask / API --> PostgreSQL
                |
    Android ----+

---

## Screenshots

### Tela inicial

![Tela inicial do Braga Budget](docs/screenshots/01-home.png)

### Gerenciamento de clientes

![Gerenciamento de clientes](docs/screenshots/02-clients.png)

### Detalhe do orçamento

![Detalhe do orçamento](docs/screenshots/03-quote-detail.png)

### Orçamento comercial

![Orçamento comercial](docs/screenshots/04-quote-pdf.png)

---

## 🔐 Privacidade e dados

Este é um repositório público.

Dados pessoais, informações comerciais e registros reais utilizados durante a operação da aplicação **não devem ser armazenados no repositório**.

Screenshots e exemplos destinados à documentação ou portfólio devem utilizar dados fictícios ou anonimizados.

Arquivos locais de banco de dados também não fazem parte do versionamento.

---

## 👨‍💻 Autor

**Diogo Zarpelão**

Desenvolvimento, arquitetura, interface, regras de aplicação, banco de dados, geração de documentos e distribuição da aplicação.

GitHub: [@diogozarpelo](https://github.com/diogozarpelo)

---

## 📊 Status do projeto

**Em desenvolvimento ativo.**

A **v1.0 local** está funcional.

O projeto continuará evoluindo com a migração da infraestrutura para nuvem, adoção de banco de dados centralizado e desenvolvimento de uma aplicação Android.

---

## 📜 Licença

O projeto ainda não possui uma licença pública definida.

Todos os direitos reservados ao autor até que uma licença seja adicionada ao repositório.