import React from 'react';
import styled, {css} from 'styled-components';
import { useNavigate } from 'react-router-dom';
import ProustImage from './assets/proust.jpg'; // Add the Proust image to your assets folder

const Container = styled.div`
  font-family: 'Georgia', serif;
  color: #333;
  background-color: #f7f4f0;
  min-height: 100vh;
  width: 100%;
  display: flex;
   flex-direction: column;
  // align-items: center;
   justify-content: center;
  padding-left: 5rem;
`;

const Header = styled.h1`
  margin-bottom: 2rem;       /* Adjust the top margin to move it closer to the top */
  margin-left: 1rem;      /* Adjust the left margin to move it horizontally */

  width: 3rem;
  font-family: "Belgrano", serif;
  font-style: normal;
  //line-height: 5rem;

  font-weight: 400;
  font-size: 4.5rem;
  //margin: 0;

  //border: 1px solid #000000;
  text-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
  
  /* PROUST GPT */
`;

const SubHeader = styled.p`
  margin-left: 1rem;
  font-size: 1.2rem;
  color: #555;
  margin-bottom: 20px;
`;

const Question = styled.p`
  font-family: 'IBM Plex Sans', serif;
  font-style: italic;
  font-weight: 400;
  margin-left: 1rem;
  font-size: 1.1rem;
  color: #8b4513;
  margin-bottom: 10px;
`;

const ButtonContainer = styled.div`
  margin-top: 1rem;
  display: flex;
  justify-content: flex-start;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 8rem;
  max-width: 45rem;   /* Set a maximum width to control wrapping */
  padding-left: 2rem;
  //margin-right: 15rem;
`;

const Button = styled.button`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;
  color: #1a1a1a;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid #8b4513;
  border-radius: 10px;
  padding: 15px;
  cursor: pointer;
  font-size: 1rem;
  width: 200px;
  text-align: center;

  &:hover {
    
    background-color: #f1ede9;
  }
  &:focus {
    outline: none;
    border-color: #8b4513;
    box-shadow: 0 0 0 3px rgba(139, 69, 19, 0.3);
  }
`;

const ProustSection = styled.div`
  //display: flex;
  //align-items: center;
  //justify-content: center;
  position: absolute;
  right: 4rem;
  top: 20rem;

  gap: 30px;
`;

const ProustImageContainer = styled.img`
  
  width: 15rem;
  height: auto;
  border-radius: 5px;
`;

const FooterLink = styled.a`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;
  font-size: 1.2rem;
  color: #333;
  text-decoration: none;
  margin-bottom: 2rem;

  &:hover {
    text-decoration: underline;
  }
`;

const LanguageSwitcher = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;

  margin-top: 1rem;
  margin-right: 3.5rem;
  position: absolute;
  top: 20px;
  right: 20px;
  font-size: 1.2rem;
`;

const LanguageLink = styled.a`
  text-decoration: none;
  color: #333;

  ${({ id }) =>
          id === '1' &&
          css`
      margin-left: 1rem;
      color: rgba(0, 0, 0, 0.2);
          `}
  
  &:hover {
    text-decoration: underline;
  }
`;

const LandingPage: React.FC = () => {

    const navigate = useNavigate();

    const handleButtonClick = (message: string) => {
        navigate('/chat', { state: { message } });
    };

    return (
        <Container>
            <LanguageSwitcher>
                <LanguageLink>INFO</LanguageLink>
                <LanguageLink id="1" href="#">FR</LanguageLink> | <LanguageLink id="2" href="#">EN</LanguageLink>
            </LanguageSwitcher>

            <Header>PROUST GPT</Header>
            <SubHeader>Explore Proust’s literature using LLM</SubHeader>
            <Question>How can I help you today?</Question>

            <ButtonContainer>
                <Button onClick={() => handleButtonClick('I would like to ask Proust to refine my prose.')}>
                    I would like to ask Proust to refine my prose.
                </Button>

                {/*<Button>I would like to ask Proust to refine my prose.</Button>*/}
                <Button>I would like to learn more about In Search of Lost Time.</Button>
                <Button>Just want to ask some questions or have a conversation.</Button>
                <Button>Tell me about a place.</Button>
                <Button>Tell me about a memory.</Button>
                <Button>Tell me about a Sunday afternoon.</Button>

            </ButtonContainer>

            <ProustSection>
                <ProustImageContainer src={ProustImage} alt="Marcel Proust" />
            </ProustSection>

            <FooterLink href="#">Combray</FooterLink>
        </Container>
    );
};

export default LandingPage;
