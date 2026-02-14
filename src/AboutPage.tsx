import React from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';

const Container = styled.div`
  font-family: 'Georgia', serif;
  color: #333;
  background-color: #f7f4f0;
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
`;

const TopBar = styled.div`
  width: 100%;
  padding: 1.25rem 2rem;
  box-sizing: border-box;
`;

const BackButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(139, 69, 19, 0.05);
  border: 1px solid #d4ccc3;
  border-radius: 20px;
  padding: 0.4rem 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8b4513;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.1);
    border-color: #8b4513;
  }
`;

const Content = styled.main`
  max-width: 700px;
  width: 100%;
  padding: 4rem 2rem 6rem;
`;

const Title = styled.h1`
  font-family: 'Belgrano', serif;
  font-weight: 400;
  font-size: 3rem;
  margin-bottom: 2.5rem;
  text-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
`;

const Section = styled.section`
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
`;

const SectionTitle = styled.h2`
  font-family: 'Belgrano', serif;
  font-weight: 400;
  font-size: 1.5rem;
  color: #8b4513;
  margin-top: 0;
  margin-bottom: 1rem;
`;

const Text = styled.p`
  line-height: 1.8;
  margin-bottom: 1rem;
  font-size: 1.05rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const Emphasis = styled.em`
  color: #8b4513;
  font-style: italic;
`;

const Footer = styled.div`
  margin-top: 1rem;
  text-align: center;
`;

const FooterLink = styled.a`
  font-family: 'IBM Plex Sans', serif;
  font-size: 1.1rem;
  color: #333;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.2s ease;

  &:hover {
    color: #8b4513;
  }
`;

const AboutPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Container>
      <TopBar>
        <BackButton onClick={() => navigate('/')}>&larr;</BackButton>
      </TopBar>

      <Content>
        <Title>About ProustGPT</Title>

        <Section>
          <SectionTitle>The Project</SectionTitle>
          <Text>
            ProustGPT is an AI-powered tool for exploring Marcel Proust's{' '}
            <Emphasis>In Search of Lost Time</Emphasis> through conversation. It
            combines intelligent passage retrieval with reflective dialogue,
            inviting you to engage with one of the greatest works of literature
            in a new way.
          </Text>
          <Text>
            Whether you are a first-time reader seeking guidance or a devoted
            Proustian revisiting familiar passages, ProustGPT meets you where
            you are and helps you discover connections, themes, and moments you
            may have missed.
          </Text>
        </Section>

        <Section>
          <SectionTitle>Marcel Proust</SectionTitle>
          <Text>
            Marcel Proust (1871–1922) spent much of his life writing{' '}
            <Emphasis>In Search of Lost Time</Emphasis>, a novel published in
            seven volumes spanning roughly 3,000 pages. It is widely regarded as
            one of the most significant works of modern literature.
          </Text>
          <Text>
            The novel traces the narrator's journey through memory, time, art,
            and love — from childhood days in the village of Combray to the
            salons of Parisian high society. Its most famous passage, the
            madeleine dipped in tea, captures the power of involuntary memory to
            collapse the distance between past and present.
          </Text>
        </Section>

        <Section>
          <SectionTitle>How It Works</SectionTitle>
          <Text>
            <strong>Explore Lost Time</strong> — Ask a question or name a theme,
            and ProustGPT searches through the full text to find relevant
            passages. It uses retrieval-augmented generation (RAG) to ground
            every response in Proust's own words.
          </Text>
          <Text>
            <strong>Reflect on My Day</strong> — Describe a moment from your
            life, and ProustGPT responds in the introspective, layered style of
            Proust himself, drawing connections between your experience and the
            themes of the novel.
          </Text>
        </Section>

        <Footer>
          <FooterLink onClick={() => navigate('/')}>
            &larr; Back to Home
          </FooterLink>
        </Footer>
      </Content>
    </Container>
  );
};

export default AboutPage;
