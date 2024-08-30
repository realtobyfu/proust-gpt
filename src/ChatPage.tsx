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
`;

const ChatArea = styled.div`
  width: 80%;
  padding: 2rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
`;

const ChatHeader = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 1.2rem;
  font-weight: 500;
  margin-bottom: 1rem;
`;

const ChatBubble = styled.div`
  background-color: rgba(255, 255, 255, 0.6);
  border: 1px solid #8b4513;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  width: fit-content;
`;

const InputArea = styled.div`
  width: 95%;
  border-radius: 20px;
  display: flex;
  align-items: center;
`;

const Input = styled.input`
  width: 100%;
  padding: 1rem;
  border: none;
  border-radius: 20px;
  font-size: 1rem;
`;

const ChatPage: React.FC = () => {
    const location = useLocation();
    const { message } = location.state || { message: 'No message received' };

    const [conversationList, setConversationList] = useState<string[]>([message]);
    const [userInput, setUserInput] = useState<string>('');

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUserInput(e.target.value);
    };

    const handleSendMessage = async () => {
        if (userInput.trim() === '') return;

        // Append user's message to the conversation list
        setConversationList((prevList) => [...prevList, `You: ${userInput}`]);

        // Send the message to the backend and get a response
        try {
            const response = await fetch('http://127.0.0.1:5000/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: userInput }),
            });

            const data = await response.json();
            const llmResponse = data.reply;

            // Append LLM's response to the conversation list
            setConversationList((prevList) => [...prevList, `ProustGPT: ${llmResponse}`]);
        } catch (error) {
            console.error('Error sending message:', error);
        }

        // Clear user input
        setUserInput('');
    };

    return (
        <ChatContainer>
            <Sidebar>
                <p><a href="#">Past Conversations</a></p>
            </Sidebar>
            <ChatArea>
                <div>
                    <ChatHeader>{message}</ChatHeader>
                    {conversationList.map((msg, index) => (
                        <ChatBubble key={index}>{msg}</ChatBubble>
                    ))}
                </div>
                <InputArea>
                    <Input
                        type="text"
                        value={userInput}
                        onChange={handleInputChange}
                        placeholder="Type your message here..."
                        onKeyPress={(e) => {
                            if (e.key === 'Enter') handleSendMessage();
                        }}
                    />
                </InputArea>
            </ChatArea>
        </ChatContainer>
    );
};

export default ChatPage;
