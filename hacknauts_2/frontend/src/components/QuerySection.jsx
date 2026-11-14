import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Loader2, MessageSquareText, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default function QuerySection({ reportId, repo, model }) {
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState([]);
  const [thinking, setThinking] = useState(false);
  const end = useRef(null);

  const send = async (e) => {
    e.preventDefault();
    const q = text.trim();
    if (!q || thinking) return;

    if (!reportId) {
      setMsgs((m) => [
        ...m,
        { role: "user", text: q },
        { role: "ai", text: "Please complete a repository analysis first, then ask questions about it." },
      ]);
      setText("");
      return;
    }

    setMsgs((m) => [...m, { role: "user", text: q }]);
    setText("");
    setThinking(true);

    try {
      const res = await api.ask(reportId, q, model);
      setMsgs((m) => [...m, { role: "ai", text: res.answer }]);
    } catch (err) {
      setMsgs((m) => [
        ...m,
        { role: "ai", text: `Error: ${err.message || "Failed to get an answer from the backend."}`, isError: true },
      ]);
    } finally {
      setThinking(false);
      setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquareText size={18} className="text-primary" /> Ask about your repository
        </CardTitle>
        <CardDescription>
          {repo
            ? `Ask why ${repo} slows down, or what a fix changed.`
            : "Analyze a repository first, then ask questions about it."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {msgs.length > 0 && (
          <div className="max-h-72 space-y-2 overflow-y-auto rounded-md bg-muted/60 p-3">
            {msgs.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : m.isError
                    ? "bg-danger/10 text-danger border border-danger/20"
                    : "bg-card text-card-foreground border"
                }`}
              >
                {m.text}
              </motion.div>
            ))}
            {thinking && (
              <p className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 size={14} className="animate-spin" /> Thinking...
              </p>
            )}
            <div ref={end} />
          </div>
        )}
        <form onSubmit={send} className="flex gap-2">
          <Input
            aria-label="Your question"
            placeholder={repo ? "Which endpoint fails first under load?" : "Analyze a repository first to enable chat"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={!repo || !reportId}
          />
          <Button type="submit" disabled={!repo || !reportId || thinking || !text.trim()}>
            {thinking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            <span>Ask</span>
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
