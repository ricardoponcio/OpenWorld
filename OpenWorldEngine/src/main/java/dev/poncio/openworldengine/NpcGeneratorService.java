package dev.poncio.openworldengine;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.UUID;

import dev.poncio.openworldengine.domain.Npc;
import org.json.JSONObject;
import java.io.File;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.Collectors;

public class NpcGeneratorService {

    public Npc generateNpc(String context) throws Exception {
        String projectDir = System.getProperty("user.dir");
        String openWorldDir = projectDir + File.separator + ".." + File.separator;
        String pythonExecutable = openWorldDir + "venv" + File.separator + "Scripts" + File.separator + "python.exe";
        String scriptPath = openWorldDir + "npc_generator.py";

        if (!new File(pythonExecutable).exists()) {
            throw new IllegalStateException("Executável do Python não encontrado. Verifique se o ambiente 'venv' foi configurado corretamente.");
        }
        if (!new File(scriptPath).exists()) {
            throw new IllegalStateException("Script Python não encontrado. Verifique o caminho: " + scriptPath);
        }

        ProcessBuilder pb = new ProcessBuilder(pythonExecutable, scriptPath, context);
        pb.environment().put("TRANSFORMERS_VERBOSITY", "error");
        pb.redirectErrorStream(true);

        Process process = pb.start();

        Future<String> stdoutFuture = Executors.newSingleThreadExecutor().submit(() -> {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                return reader.lines().collect(Collectors.joining("\n"));
            }
        });

        Future<String> stderrFuture = Executors.newSingleThreadExecutor().submit(() -> {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getErrorStream()))) {
                return reader.lines().collect(Collectors.joining("\n"));
            }
        });

        int exitCode = process.waitFor();
        System.out.println("Script Python finalizado com código: " + exitCode);

        String stdout = "";
        String stderr = "";
        try {
            stdout = stdoutFuture.get();
            stderr = stderrFuture.get();
        } catch (Exception e) {
            e.printStackTrace();
        }

        if (exitCode == 0) {
            if (stdout.isEmpty()) {
                throw new Exception("Saída JSON não encontrada.");
            } else {
                final var cleaned = stdout.substring(stdout.indexOf("{"));
                JSONObject jsonNpc = new JSONObject(cleaned);
                String id = UUID.randomUUID().toString();
                String nome = jsonNpc.getString("nome");
                int idade = jsonNpc.getInt("idade");
                String trabalho = jsonNpc.getString("trabalho");
                String habitacao = jsonNpc.getString("habitacao");
                String personalidade = jsonNpc.getString("personalidade");
                return new Npc(id, nome, idade, trabalho, habitacao, personalidade, null, null);
            }
        } else {
            throw new Exception("O comando falhou com o código de saída: " + exitCode);
        }
    }
}