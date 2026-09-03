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

## 🗺️ Roadmap

### ✅ v1.0 — Aplicação local

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

### ☁️ Próxima etapa — Cloud

- [ ] Migrar o banco de dados para PostgreSQL
- [ ] Hospedar o backend
- [ ] Centralizar os dados
- [ ] Implementar autenticação
- [ ] Preparar endpoints de API
- [ ] Adaptar o sistema web para operação online
- [ ] Preparar infraestrutura para múltiplos dispositivos

### 📱 v2.0 — Android

- [ ] Desenvolver aplicativo Android
- [ ] Criar orçamentos pelo celular
- [ ] Consultar clientes e orçamentos
- [ ] Consumir a API central
- [ ] Sincronizar web e mobile
- [ ] Compartilhar PDF e imagem pelo dispositivo móvel

Arquitetura planejada:

```text
Web ───────┐
           │
           ├── Flask / API ─── PostgreSQL
           │
Android ───┘
```

---

## 📸 Screenshots

A documentação visual do projeto será adicionada gradualmente.

Imagens planejadas:

- página inicial
- gerenciamento de clientes
- gerenciamento de componentes
- criação do orçamento
- composição dos itens
- mão de obra individual
- resumo do orçamento
- orçamento emitido
- PDF comercial

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