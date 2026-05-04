import { expect } from "chai";
import hre from "hardhat"; 
const { ethers } = hre;

describe("Sistema Gestione Tirocinio", function () {
  let nftSkill, skillSelection, userStories;
  let owner, developer;

  // Si resetta tutto prima di ogni test per evitare interferenze
  beforeEach(async function () {
    // Prende gli account: il primo (0) è l'owner, il secondo (1) il dev
    [owner, developer] = await ethers.getSigners();

    // --- 1. Deploy NFTSkill (Il DB delle competenze) ---
    const NFTSkillFactory = await ethers.getContractFactory("Skill");
    nftSkill = await NFTSkillFactory.deploy(); // Non ha parametri nel costruttore
    await nftSkill.waitForDeployment();

    // --- 2. Deploy SkillSelection (La selezione/hiring) ---
    const SkillSelectionFactory = await ethers.getContractFactory("SkillSelection");
    const duration = 60; // Parametro 1: durata (minuti)
    const requiredSkills = [1, 2, 3]; // Parametro 2: lista ID skill cercate
    
    // Passa i dati al constructor di Hiring_Smart_Contract.sol
    skillSelection = await SkillSelectionFactory.deploy(duration, requiredSkills);
    await skillSelection.waitForDeployment();

    // --- 3. Deploy UserStories (Task e soldi) ---
    const UserStoriesFactory = await ethers.getContractFactory("UserStories");
    const usSkills = [[1, 2], [3]]; // Task 0: skill 1,2 | Task 1: skill 3
    const usEffort = [10, 20]; // Difficoltà dei task
    const usPayment = [
      ethers.parseEther("0.1"), // Trasforma 0.1 ETH in Wei (numero con 18 zeri)
      ethers.parseEther("0.2")
    ];

    // Passa i dati al constructor di UserStories_SC.sol
    userStories = await UserStoriesFactory.deploy(usSkills, usEffort, usPayment);
    await userStories.waitForDeployment();
  });

  // TEST 1: Controllo permessi
  it("Dovrebbe impostare l'owner corretto su UserStories", async function () {
    // Verifica che l'indirizzo dell'owner sia quello di chi ha fatto il deploy
    expect(await userStories.owner()).to.equal(owner.address);
  });

  // TEST 2: Controllo dati iniziali
  it("Dovrebbe avere il numero corretto di User Stories iniziali", async function () {
    const dim = await userStories.dimUSList();
    // 2n indica un BigInt (necessario per i numeri uint256 di Solidity)
    expect(dim).to.equal(2n); 
  });

  // TEST 3: Controllo logica Hiring
  it("SkillSelection dovrebbe avere la lista skill corretta", async function () {
    const list = await skillSelection.getSkillList();
    // Converte i BigInt della blockchain in numeri JS per confrontarli
    const listNumbers = list.map(n => Number(n));
    // deep.equal serve per confrontare il contenuto di un array
    expect(listNumbers).to.deep.equal([1, 2, 3]);
  });
});