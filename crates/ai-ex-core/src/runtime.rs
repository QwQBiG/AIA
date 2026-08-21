use ai_ex_domain::{AppError, ConversationState, Message, Role, SystemEvent, TurnId};
use ai_ex_text::ResponsePreamble;

use crate::{
    AvatarPort, ConversationEngine, ConversationPolicy, EventSink, LanguageModelPort,
    MemoryPort, ModelRequest, SpeechPort,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeControl
{
    Interrupt { reason: String },
    Shutdown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TurnOutcome
{
    Completed(TurnId),
    Interrupted(TurnId),
    Shutdown(TurnId),
}

enum NextInput
{
    Model(Option<Result<String, AppError>>),
    Control(Option<RuntimeControl>),
}

pub struct Runtime<M, S, A, N, E>
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    engine: ConversationEngine,
    model: M,
    speech: S,
    avatar: A,
    memory: N,
    events: E,
    system_prompt: String,
    memory_recall_limit: usize,
}

impl<M, S, A, N, E> Runtime<M, S, A, N, E>
where
    M: LanguageModelPort,
    S: SpeechPort,
    A: AvatarPort,
    N: MemoryPort,
    E: EventSink,
{
    pub fn new(model: M, speech: S, avatar: A, memory: N, events: E) -> Self
    {
        Self::from_policy(
            model,
            speech,
            avatar,
            memory,
            events,
            ConversationPolicy::default(),
        )
    }

    pub fn with_policy(
        model: M,
        speech: S,
        avatar: A,
        memory: N,
        events: E,
        policy: ConversationPolicy,
    ) -> Result<Self, AppError>
    {
        policy.validate()?;
        Ok(Self::from_policy(model, speech, avatar, memory, events, policy))
    }

    fn from_policy(
        model: M,
        speech: S,
        avatar: A,
        memory: N,
        events: E,
        policy: ConversationPolicy,
    ) -> Self
    {
        Self {
            engine: ConversationEngine::with_history_turn_limit(policy.history_turn_limit),
            model,
            speech,
            avatar,
            memory,
            events,
            system_prompt: policy.system_prompt,
            memory_recall_limit: policy.memory_recall_limit,
        }
    }

    pub fn set_system_prompt(&mut self, prompt: impl Into<String>) -> Result<(), AppError>
    {
        if self.engine.active_turn().is_some()
        {
            return Err(AppError::invalid_transition("cannot change persona during an active turn"));
        }
        let prompt = prompt.into();
        if prompt.chars().count() > 16_384
        {
            return Err(AppError::configuration("system prompt is too long"));
        }
        self.system_prompt = prompt;
        Ok(())
    }

    pub fn state(&self) -> ConversationState
    {
        self.engine.state()
    }

    pub async fn run_turn(&mut self, input: impl Into<String>) -> Result<TurnId, AppError>
    {
        match self.run_turn_inner(input.into(), None).await?
        {
            TurnOutcome::Completed(turn_id) => Ok(turn_id),
            TurnOutcome::Interrupted(_) | TurnOutcome::Shutdown(_) => Err(
                AppError::invalid_transition("uncontrolled turn ended by control input"),
            ),
        }
    }

    pub async fn run_turn_controlled(
        &mut self,
        input: impl Into<String>,
        control: &mut tokio::sync::mpsc::Receiver<RuntimeControl>,
    ) -> Result<TurnOutcome, AppError>
    {
        self.run_turn_inner(input.into(), Some(control)).await
    }

    async fn run_turn_inner(
        &mut self,
        input: String,
        mut control: Option<&mut tokio::sync::mpsc::Receiver<RuntimeControl>>,
    ) -> Result<TurnOutcome, AppError>
    {
        let memories = self
            .memory
            .recall_for_context(&input, self.memory_recall_limit)
            .await?;
        let turn_id = self.engine.begin_turn(&input)?;
        let mut messages = Vec::new();
        if !self.system_prompt.trim().is_empty()
        {
            messages.push(Message::new(Role::System, self.system_prompt.clone()));
        }
        messages.extend(memories);
        messages.extend_from_slice(self.engine.history());
        let request = ModelRequest {
            turn_id,
            messages,
        };
        self.dispatch_events().await?;

        let mut stream = match self.model.stream(request).await
        {
            Ok(stream) => stream,
            Err(error) =>
            {
                self.engine.fail(error.to_string());
                self.dispatch_events().await?;
                return Err(error);
            }
        };
        let mut preamble = ResponsePreamble::default();

        loop
        {
            let next = if let Some(receiver) = control.as_deref_mut()
            {
                tokio::select!
                {
                    item = stream.recv() => NextInput::Model(item),
                    command = receiver.recv() => NextInput::Control(command),
                }
            }
            else
            {
                NextInput::Model(stream.recv().await)
            };

            match next
            {
                NextInput::Model(Some(Ok(chunk))) =>
                {
                    let output = preamble.push(&chunk);
                    if let Some(emotion) = output.emotion
                    {
                        self.engine.set_emotion(turn_id, emotion)?;
                    }
                    if !output.text.is_empty()
                    {
                        self.engine.accept_chunk(turn_id, &output.text)?;
                    }
                    self.dispatch_events().await?;
                }
                NextInput::Model(Some(Err(error))) =>
                {
                    self.engine.fail(error.to_string());
                    self.dispatch_events().await?;
                    return Err(error);
                }
                NextInput::Model(None) =>
                {
                    let trailing = preamble.finish();
                    if !trailing.is_empty()
                    {
                        self.engine.accept_chunk(turn_id, &trailing)?;
                        self.dispatch_events().await?;
                    }
                    break;
                }
                NextInput::Control(Some(RuntimeControl::Interrupt { reason })) =>
                {
                    self.interrupt(reason).await?;
                    return Ok(TurnOutcome::Interrupted(turn_id));
                }
                NextInput::Control(Some(RuntimeControl::Shutdown)) =>
                {
                    self.interrupt("runtime shutdown").await?;
                    return Ok(TurnOutcome::Shutdown(turn_id));
                }
                NextInput::Control(None) => control = None,
            }
        }

        let assistant = self.engine.finish_turn(turn_id)?;
        self.memory.remember(turn_id, input, assistant).await?;
        self.dispatch_events().await?;
        Ok(TurnOutcome::Completed(turn_id))
    }

    pub async fn interrupt(&mut self, reason: impl Into<String>) -> Result<(), AppError>
    {
        let active = self.engine.active_turn().ok_or_else(|| {
            AppError::invalid_transition("there is no active turn")
        })?;
        self.model.cancel(active).await?;
        self.speech.interrupt().await?;
        self.avatar.set_neutral().await?;
        self.engine.interrupt(reason)?;
        self.dispatch_events().await
    }

    pub async fn stop(&mut self) -> Result<(), AppError>
    {
        if let Some(active) = self.engine.active_turn()
        {
            self.model.cancel(active).await?;
            self.engine.interrupt("runtime stopped")?;
        }
        self.speech.interrupt().await?;
        self.avatar.set_neutral().await?;
        self.engine.stop();
        self.dispatch_events().await
    }

    async fn dispatch_events(&mut self) -> Result<(), AppError>
    {
        for event in self.engine.drain_events()
        {
            match &event
            {
                SystemEvent::SentenceReady { turn_id, text } =>
                {
                    self.speech.enqueue(*turn_id, text.clone()).await?;
                    self.avatar.set_speaking(true).await?;
                }
                SystemEvent::EmotionChanged { emotion, .. } =>
                {
                    self.avatar.set_emotion(*emotion).await?;
                }
                SystemEvent::TurnFinished { .. } | SystemEvent::TurnInterrupted { .. } =>
                {
                    self.avatar.set_neutral().await?;
                }
                SystemEvent::Fault { .. } =>
                {
                    self.speech.interrupt().await?;
                    self.avatar.set_neutral().await?;
                }
                _ =>
                {
                }
            }
            self.events.publish(event).await;
        }
        Ok(())
    }
}
