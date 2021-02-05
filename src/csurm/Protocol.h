#ifndef CSURM_PROTOCOL_H
#define CSURM_PROTOCOL_H

namespace csurm {

class Command {
public:
  Command();
  ~Command();
};

class Query : public Command {
public:
  Query();
};

}

#endif //CSURM_PROTOCOL_H
