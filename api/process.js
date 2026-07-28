import { OpenAI } from 'openai';
import ytdl from 'ytdl-core';
import { put } from '@vercel/blob';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegStatic from 'ffmpeg-static';
import { PassThrough } from 'stream';

ffmpeg.setFfmpegPath(ffmpegStatic);

export const config = {
  api: {
    bodyParser: {
      sizeLimit: '50mb'
    },
    responseLimit: '50mb'
  }
};

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { videoId, openaiKey, action } = req.body;
  
  if (!videoId || !openaiKey) {
    return res.status(400).json({ error: 'videoId e openaiKey são obrigatórios' });
  }

  const openai = new OpenAI({ apiKey: openaiKey });

  try {
    switch (action) {
      case 'download':
        return await handleDownload(res, videoId);
      case 'transcribe':
        return await handleTranscribe(res, videoId, openai);
      case 'analyze':
        return await handleAnalyze(res, req.body.transcript, req.body.title, openai);
      case 'full':
        return await handleFullProcess(res, videoId, openai);
      default:
        return res.status(400).json({ error: 'Ação inválida' });
    }
  } catch (error) {
    console.error('Erro:', error);
    return res.status(500).json({ 
      error: error.message,
      step: error.step || 'unknown'
    });
  }
}

async function handleDownload(res, videoId) {
  try {
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    
    // Baixar apenas áudio para transcrição
    const audioStream = ytdl(videoUrl, {
      quality: 'lowestaudio',
      filter: 'audioonly'
    });

    const chunks = [];
    for await (const chunk of audioStream) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);

    // Upload para Vercel Blob
    const blob = await put(`audio-${videoId}.mp3`, buffer, {
      access: 'public',
      contentType: 'audio/mpeg'
    });

    return res.status(200).json({ 
      success: true, 
      audioUrl: blob.url,
      size: buffer.length
    });
  } catch (error) {
    throw { ...error, step: 'download' };
  }
}

async function handleTranscribe(res, videoId, openai) {
  try {
    // Primeiro, baixar o áudio
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const audioStream = ytdl(videoUrl, {
      quality: 'lowestaudio',
      filter: 'audioonly'
    });

    const chunks = [];
    for await (const chunk of audioStream) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);

    // Criar arquivo temporário para enviar para OpenAI
    const audioFile = new File([buffer], 'audio.mp3', { type: 'audio/mpeg' });

    // Transcrever com Whisper
    const transcription = await openai.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      response_format: 'verbose_json',
      language: 'pt'
    });

    return res.status(200).json({
      success: true,
      transcription: transcription.text,
      segments: transcription.segments
    });
  } catch (error) {
    throw { ...error, step: 'transcribe' };
  }
}

async function handleAnalyze(res, transcript, title, openai) {
  try {
    const prompt = `Você é um editor de vídeos profissional especializado em criar shorts virais.

Analise a transcrição abaixo e identifique os MELHORES momentos para shorts.

CRITÉRIOS:
1. Gancho forte nos primeiros 3 segundos
2. Duração ideal: 30-60 segundos
3. Conteúdo independente
4. Alto potencial de engajamento
5. Momento com clímax

TÍTULO: ${title}

TRANSCRIÇÃO:
${transcript}

Responda APENAS com JSON:
[
  {
    "inicio": 60.0,
    "fim": 115.0,
    "titulo_gancho": "Título viral",
    "descricao": "Descrição do clipe",
    "virality": 8.5
  }
]

Selecione 3-5 melhores momentos.`;

    const completion = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages: [
        { role: 'system', content: 'Responda apenas com JSON válido.' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.7
    });

    const content = completion.choices[0].message.content;
    const jsonMatch = content.match(/\[[\s\S]*\]/);
    
    if (!jsonMatch) throw new Error('Formato de resposta inválido');
    
    const clips = JSON.parse(jsonMatch[0]);
    
    return res.status(200).json({
      success: true,
      clips: clips
    });
  } catch (error) {
    throw { ...error, step: 'analyze' };
  }
}

async function handleFullProcess(res, videoId, openai) {
  try {
    // 1. Download do áudio
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const audioStream = ytdl(videoUrl, {
      quality: 'lowestaudio',
      filter: 'audioonly'
    });

    const chunks = [];
    for await (const chunk of audioStream) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);

    // 2. Transcrição
    const audioFile = new File([buffer], 'audio.mp3', { type: 'audio/mpeg' });
    const transcription = await openai.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      response_format: 'verbose_json',
      language: 'pt'
    });

    // 3. Análise
    const prompt = `Analise esta transcrição e identifique os 3-5 melhores momentos para shorts virais.

TÍTULO: Vídeo do YouTube

TRANSCRIÇÃO:
${transcription.text}

Responda APENAS com JSON no formato:
[{"inicio": 0.0, "fim": 0.0, "titulo_gancho": "", "descricao": "", "virality": 0.0}]`;

    const completion = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages: [
        { role: 'system', content: 'Responda apenas com JSON válido.' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.7
    });

    const content = completion.choices[0].message.content;
    const jsonMatch = content.match(/\[[\s\S]*\]/);
    const clips = jsonMatch ? JSON.parse(jsonMatch[0]) : [];

    return res.status(200).json({
      success: true,
      transcription: transcription.text,
      clips: clips,
      stats: {
        duration: transcription.segments[transcription.segments.length - 1]?.end || 0,
        segments: transcription.segments.length,
        clips_found: clips.length
      }
    });
  } catch (error) {
    throw { ...error, step: error.step || 'full_process' };
  }
}