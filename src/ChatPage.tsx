import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import styled from 'styled-components';

const ChatContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: #f7f4f0;
`;

const Sidebar = styled.div`
  width: 20%;
  background-color: #fff;
  border-right: 1px solid #ccc;
  padding: 2rem;
  box-sizing: border-box;
  color: #333;
`;

const ChatArea = styled.div`
  width: 80%;
  padding: 2rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: #333;
`;

const ChatMode = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 1rem;
  font-weight: 400;
  color: #555;
  margin-bottom: 10px;
`;

// General ChatBubble styling
const ChatBubble = styled.div<{ isUser: boolean }>`
  background-color: ${(props) => ('rgba(255, 255, 255, 0.6)')}; /* User messages and Proust responses */
  border: ${(props) => ('none')}; /* No outline for user messages */
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: 60%; /* Ensure bubbles don't take full width */
  align-self: ${(props) => (props.isUser ? 'flex-start' : 'flex-end')}; /* Align user messages to the left, Proust to the right */
  margin-left: ${(props) => (props.isUser ? '0' : 'auto')}; /* Give space on the left for Proust */
  margin-right: ${(props) => (props.isUser ? 'auto' : '0')}; /* Give space on the right for user */
  color: #333; /* Text color */
`;

const InputArea = styled.div`
  width: 95%;
  border-radius: 20px;
  display: flex;
  align-items: center;
  position: relative;
`;

const Input = styled.input`
  width: 100%;
  padding: 1rem;
  border: none;
  border-radius: 20px;
  font-size: 1rem;
  color: #333;
  background-color: #fff;
`;

const LoadingIndicator = styled.div`
  position: absolute;
  right: 1rem;
  font-size: 0.9rem;
  color: #8b4513;
`;

const ChatPage: React.FC = () => {
    const location = useLocation();
    const { mode, prompt } = location.state || { mode: 'qa', prompt: '' };

    // Initialize conversation list based on whether the prompt is empty
    const initialConversation = prompt ? [`You: ${prompt}`] : [];
    const [conversationList, setConversationList] = useState<string[]>(initialConversation);
    const [userInput, setUserInput] = useState<string>('');
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [initialPromptSent, setInitialPromptSent] = useState<boolean>(false);

    // Map mode to display string
    const getModeDisplayString = (mode: string) => {
        switch (mode) {
            case 'qa':
                return 'Q & A';
            case 'explore_lost_time':
                return 'Explore In Search of Lost Time';
            case 'refine_prose':
                return 'Refine Prose';
            default:
                return 'Q & A'; // Default mode if unknown
        }
    };

    const modeDisplayString = getModeDisplayString(mode);

    useEffect(() => {
        if (prompt && prompt.trim() !== '' && !initialPromptSent) {
            console.log("Sending initial prompt to backend:", prompt);
            setIsLoading(true);
            sendMessageToBackend(prompt);
            setInitialPromptSent(true);  // Ensure this prompt is only sent once
        }
    }, [prompt, initialPromptSent]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUserInput(e.target.value);
    };

    const handleSendMessage = async () => {
        if (userInput.trim() === '') return;

        // Append user's message to the conversation list
        setConversationList((prevList) => [...prevList, `You: ${userInput}`]);

        // Set loading state to true to show loading indicator and disable input
        setIsLoading(true);

        // Send the message to the backend and get a response
        sendMessageToBackend(userInput);

        // Clear user input
        setUserInput('');
    };

    const sendMessageToBackend = async (message: string) => {
        console.log("Sending message to backend:", message);
        let apiEndpoint = '';

        // Determine which API route to call based on the mode
        switch (mode) {
            case 'qa':
                apiEndpoint = 'http://127.0.0.1:5000/api/qa';
                break;
            case 'explore_lost_time':
                apiEndpoint = 'http://127.0.0.1:5000/api/explore_lost_time';
                break;
            case 'refine_prose':
                apiEndpoint = 'http://127.0.0.1:5000/api/refine_prose';
                break;
            default:
                apiEndpoint = 'http://127.0.0.1:5000/api/qa'; // Default route
        }

        try {
            const response = await fetch(apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),  // No mode included here
            });

            const data = await response.json();
            const llmResponse = data.reply;

            // Append LLM's response to the conversation list
            setConversationList((prevList) => [...prevList, `ProustGPT: ${llmResponse}`]);
        } catch (error) {
            console.error('Error sending message:', error);
            setConversationList((prevList) => [
                ...prevList,
                'ProustGPT: Sorry, there was an error processing your message.',
            ]);
        }

        // Set loading state to false
        setIsLoading(false);
    };

    return (
        <ChatContainer>
            <Sidebar>
                <p><a href="#" style={{ color: '#333', textDecoration: 'none' }}>Past Conversations</a></p>
            </Sidebar>
            <ChatArea>
                <div>
                    {/* Display the mode at the top */}
                    <ChatMode>Mode: {modeDisplayString}</ChatMode>

                    {conversationList.map((msg, index) => {
                        const isUser = msg.startsWith('You:'); // Check if message is from the user
                        const messageText = isUser ? msg.replace('You: ', '') : msg.replace('ProustGPT: ', ''); // Remove the prefix
                        return (
                            <ChatBubble key={index} isUser={isUser}>
                                {messageText}
                            </ChatBubble>
                        );
                    })}

                    {isLoading && <LoadingIndicator>Loading...</LoadingIndicator>}
                </div>
                <InputArea>
                    <Input
                        type="text"
                        value={userInput}
                        onChange={handleInputChange}
                        placeholder="Type your message here..."
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !isLoading) handleSendMessage();
                        }}
                        disabled={isLoading}
                    />
                </InputArea>
            </ChatArea>
        </ChatContainer>
    );
};

export default ChatPage;
