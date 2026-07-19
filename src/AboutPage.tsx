import React from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import LanguageSwitcher from './components/LanguageSwitcher';
import { useLanguage } from './contexts/LanguageContext';

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
  display: flex;
  justify-content: space-between;
  align-items: center;
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

  a {
    color: inherit;
    text-decoration: underline;
  }

  &:last-child {
    margin-bottom: 0;
  }
`;


const Footer = styled.div`
  margin-top: 1rem;
  text-align: center;
`;

const Credit = styled.div`
  margin-top: 2rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #999;

  a {
    color: #999;
    text-decoration: none;
    transition: color 0.2s ease;

    &:hover {
      color: #8b4513;
    }
  }
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

const TranslationBlock = styled.div`
  text-align: center;
  line-height: 2;
`;

const TranslationTitle = styled.div`
  font-family: 'Belgrano', serif;
  font-size: 1.1rem;
  letter-spacing: 0.05em;
  color: #8b4513;
  margin-bottom: 0.25rem;
`;

const TranslationSubtitle = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #999;
  letter-spacing: 0.03em;
  margin-bottom: 0.75rem;
`;

const TranslationDetail = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.95rem;
  color: #555;
  line-height: 1.8;
`;

const AboutPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { language } = useLanguage();

  return (
    <Container>
      <TopBar>
        <BackButton onClick={() => navigate('/')}>&larr;</BackButton>
        <LanguageSwitcher />
      </TopBar>

      <Content>
        <Title>{t('about.title')}</Title>

        <Section>
          <SectionTitle>{t('about.theProject')}</SectionTitle>
          <Text>
            <Trans i18nKey="about.projectDesc1" components={{ em: <em /> }} />
          </Text>
          <Text>
            {t('about.projectDesc2')}
          </Text>
          <Text>
            <Trans
              i18nKey="about.madeBy"
              components={[<a href="https://tobiasfu.com" target="_blank" rel="noopener noreferrer" />]}
            />
          </Text>
        </Section>

        <Section>
          <SectionTitle>{t('about.marcelProust')}</SectionTitle>
          <Text>
            <Trans i18nKey="about.proustDesc1" components={{ em: <em /> }} />
          </Text>
          <Text>
            {t('about.proustDesc2')}
          </Text>
        </Section>

        <Section>
          <SectionTitle>{t('about.howItWorks')}</SectionTitle>
          <Text>
            <Trans i18nKey="about.exploreLostTime" components={{ strong: <strong /> }} />
          </Text>
          <Text>
            <Trans i18nKey="about.reflectOnMyDay" components={{ strong: <strong /> }} />
          </Text>
        </Section>

        <Section>
          <SectionTitle>{t('about.bilingualTitle')}</SectionTitle>
          <Text>{t('about.bilingualDesc')}</Text>
        </Section>

        {language === 'en' && (
          <Section>
            <SectionTitle>{t('about.translationTitle')}</SectionTitle>
            <TranslationBlock>
              <TranslationTitle>{t('about.translationWork')}</TranslationTitle>
              <TranslationSubtitle>{t('about.translationVolumes')}</TranslationSubtitle>
              <TranslationDetail>
                {t('about.translationOriginal')}<br />
                {t('about.translationMoncrieff')}<br />
                {t('about.translationSchiff')}<br />
                {t('about.translationPublisher')}
              </TranslationDetail>
            </TranslationBlock>
          </Section>
        )}

        <Footer>
          <FooterLink onClick={() => navigate('/')}>
            &larr; {t('about.backToHome')}
          </FooterLink>
          <Credit>
            <Trans
              i18nKey="about.madeBy"
              components={[<a href="https://tobiasfu.com" target="_blank" rel="noopener noreferrer" />]}
            />
          </Credit>
        </Footer>
      </Content>
    </Container>
  );
};

export default AboutPage;
