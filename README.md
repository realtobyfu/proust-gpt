Initial Screen:
![screenshot](screenshot-1.png)


# ProustGPT Chat Application

**ProustGPT** is a conversational web application inspired by Marcel Proust and powered by a LLM.
It currently supports modes:

1. **Explore Lost Time**: Retrieve relevant passages from *In Search of Lost Time* using Retrieval-Augmented Generation (RAG).
2. **Reflect on My Day**: Engage in thoughtful and introspective conversation to reflect on daily experiences.

## Features

### Explore Lost Time (RAG)
- Enter a query to explore related passages from Proust's novel, *In Search of Lost Time*.
- Passages are retrieved based on semantic similarity using Sentence Transformers and vector search.

### Reflect on My Day
- Engage in introspective conversation with prompts designed to help you reflect on your daily experiences.

## Technology Stack

### Frontend
- **React**
- **Styled Components**
- **React Router**

### Backend
- **Flask**
- **llama_cpp** (for the LLaMA model)
- **Sentence Transformers** (for semantic embedding and retrieval)

## Installation

### Prerequisites

- **Node.js** (version 16+ recommended)
- **Python 3.x** (recommended 3.8+)
- **virtualenv** (for managing Python virtual environments)
- A compatible LLaMA model installed locally (e.g., `Meta-Llama-3-8B-Instruct-Q4_K_M.gguf`)

## Step-by-Step Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/realtobyfu/proust-gpt.git
cd proust-gpt
```

### Step 2: Set Up the Backend

#### Create and Activate Virtual Environment

Navigate to the backend directory:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

Once activated, your terminal prompt will include `(venv)`.

#### Install Python Dependencies

Run the following command to install backend dependencies:

```bash
pip install -r requirements.txt
```

Ensure that the LLaMA model is placed at the correct location as specified in `server.py`:

```python
model_path = "/path/to/your/llama/model/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
```

#### Run the Backend

In your activated environment, run:

```bash
flask run
```

The backend will start running at `http://127.0.0.1:5000`.

### Setup the Frontend

Open a new terminal and navigate to the frontend directory:

```bash
cd frontend
npm install
npm start
```

The frontend will start running at `http://localhost:3000`.

## Usage

With both frontend and backend running, open your browser at `http://localhost:3000`.

Choose between:

- **Explore Lost Time**: Enter queries to explore Marcel Proust's text.
- **Reflect on My Day**: Converse with ProustGPT for reflective guidance.

## Backend API Routes

- **`/api/explore_lost_time`** *(POST)*
  - Retrieves passages from *In Search of Lost Time* relevant to your query.

- **`/api/reflect` (POST)**
  - Provides reflective responses to your messages without retrieval from external sources.

## Project Structure

```
├── backend
│   ├── app.py                 # Main Flask application
│   ├── parsed.json            # Parsed text data
│   ├── requirements.txt       # Python dependencies
├── frontend
│   ├── public
│   ├── src
│   │   ├── components
│   │   │   ├── ChatPage.tsx   # Main chat page
│   │   └── App.tsx            # React app entry point
│   ├── assets
│   ├── package.json           # Frontend dependencies
│   └── tsconfig.json          # TypeScript configuration
└── README.md                  # Project documentation
```

## Work in Progress

- [ ] Complete the 'Combray' gallery page
- [ ] Add conversation history support
- [ ] Add a French-language interface

## Future Improvements

- Improve semantic retrieval for better context in **Explore Lost Time**.
- Fine-tune the reflective prompts for a deeper and richer conversational experience.
- Expand corpus with additional relevant documents.

## License

This project is licensed under the [Apache 2.0 License](LICENSE).

## Acknowledgments

- **Meta (LLaMA)**: For providing the large language model.
- **Sentence Transformers**: For the powerful embeddings.
- The open-source community for helpful libraries and inspiration.

---

Enjoy your thoughtful conversations with ProustGPT! 🌸📖✨
```