// Main.rs
use fluxer_core::client::{Client, ClientOptions};
use fluxer_core::client::typed_events::DispatchEvent;
use fluxer_builders::{EmbedBuilder, MessagePayload};
use fluxer_rest::Rest;



const COMMAND_PREFIX: &str = "/";
const _BOT_NAME: &str = "Music Link Converter";


#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();
    tracing_subscriber::fmt().with_env_filter("info").init();

    let token = std::env::var("FLUXER_TOKEN").expect("FLUXER_TOKEN must be set in the environment or .env file");

    let options = ClientOptions {
        intents: 0,
        wait_for_guilds: true,
        ..Default::default()
    };

    let mut client = Client::new(options);
    let rest: Rest = client.rest.clone();

    client.on_typed(move |event| {
        let rest = rest.clone();
        Box::pin(async move {
            match event {
                DispatchEvent::Ready => {
                    tracing::info!("Bot is ready");
                }

                DispatchEvent::MessageCreate { message, .. } => {
                    if message.content.trim() == format!("{COMMAND_PREFIX}ping") {
                        let embed = EmbedBuilder::new()
                            .title("Pong!")
                            .color(0x5865F2)
                            .build();

                        let payload = MessagePayload::new().add_embed(embed).build();

                        if let Err(e) = message.send(&rest, &payload).await {
                            tracing::error!("send: {e}");
                        }
                    } 
                }
                _ => {}
            }
        })
    });

    if let Err(e) = client.login(&token).await {
        tracing::error!("login: {e:?}");
    }
}